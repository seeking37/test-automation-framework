from common.sendrequest import SendRequest
from common.recordlog import logs
from conf.operationConfig import OperationConfig
from common.assertions import Assertions
from common.debugtalk import DebugTalk
import allure
import json
import jsonpath
import re
import traceback
from json.decoder import JSONDecodeError

assert_res = Assertions()


class RequestBase(object):
    def __init__(self):
        self.run = SendRequest()
        self.read = ReadYamlData()
        self.conf = OperationConfig()

    @staticmethod
    def handler_yaml_list(data_dict):
        # 在replace_load中被调用，没有找到具体例子。
        """处理yaml文件测试用例请求参数为list情况，以数组形式"""
        try:
            for key, value in data_dict.items():
                if isinstance(value, list):
                    value_lst = ','.join(value).split(',')
                    data_dict[key] = value_lst
                return data_dict
        except Exception:
            logs.error(str(traceback.format_exc()))

    def replace_load(self, data):
        """yaml数据替换解析"""
        str_data = data
        if not isinstance(data, str):
            str_data = json.dumps(data, ensure_ascii=False)
        for i in range(str_data.count('${')):
            if '${' in str_data and '}' in str_data:
                # index检测字符串是否子字符串，并找到字符串的索引位置
                start_index = str_data.index('$')
                end_index = str_data.index('}', start_index)
                # yaml文件的参数，如：${get_yaml_data(loginname)}
                ref_all_params = str_data[start_index:end_index + 1]
                # 函数名，获取Debugtalk的方法
                func_name = ref_all_params[2:ref_all_params.index("(")]
                # 函数里的参数
                func_params = ref_all_params[ref_all_params.index("(") + 1:ref_all_params.index(")")]
                # 传入替换的参数获取对应的值,*func_params按,分割重新得到一个字符串
                extract_data = getattr(DebugTalk(), func_name)(*func_params.split(',') if func_params else "")
                if extract_data and isinstance(extract_data, list):
                    extract_data = ','.join(e for e in extract_data)
                str_data = str_data.replace(ref_all_params, str(extract_data))
        # 还原数据
        if data and isinstance(data, dict):
            data = json.loads(str_data)
            self.handler_yaml_list(data)
        else:
            data = str_data
        return data

    def specification_yaml(self, case_info):
        """
        规范yaml测试用例的写法
        :param case_info: list类型,调试取case_info[0]-->dict
        :return:
        """
        params_type = ['params', 'data', 'json']
        cookie = None
        try:
            base_url = self.conf.get_section_for_data('api_envi', 'host')
            # base_url = self.replace_load(case_info['baseInfo']['url'])
            url = base_url + case_info["baseInfo"]["url"]
            allure.attach(url, f'接口地址：{url}')
            api_name = case_info["baseInfo"]["api_name"]
            allure.attach(api_name, f'接口名：{api_name}')
            method = case_info["baseInfo"]["method"]
            allure.attach(method, f'请求方法：{method}')
            header = self.replace_load(case_info["baseInfo"]["header"])
            allure.attach(str(header), '请求头信息', allure.attachment_type.TEXT)
            try:
                cookie = self.replace_load(case_info["baseInfo"]["cookies"])
                allure.attach(str(cookie), 'Cookie', allure.attachment_type.TEXT)
            except:
                pass
            for tc in case_info["testCase"]:
                case_name = tc.pop("case_name")
                allure.attach(case_name, f'测试用例名称：{case_name}', allure.attachment_type.TEXT)
                # 断言结果解析替换
                val = self.replace_load(tc.get('validation'))
                tc['validation'] = val
                # 字符串形式的列表转换为list类型
                validation = eval(tc.pop('validation'))
                allure_validation = str([str(list(i.values())) for i in validation])
                allure.attach(allure_validation, "预期结果", allure.attachment_type.TEXT)
                extract = tc.pop('extract', None)
                extract_lst = tc.pop('extract_list', None)  # {'goodsIds': '$.goodsList[*].goodsId'}
                for key, value in tc.items(): # key:'params', valu:{'msgType': 'getHandsetListOfCust', 'page': 1, 'size': 20}
                    if key in params_type:
                        tc[key] = self.replace_load(value)
                file, files = tc.pop("files", None), None
                if file is not None:
                    for fk, fv in file.items():
                        allure.attach(json.dumps(file), '导入文件')
                        files = {fk: open(fv, 'rb')}
                res = self.run.run_main(name=api_name,
                                        url=url,
                                        case_name=case_name,
                                        header=header,
                                        cookies=cookie,
                                        method=method,
                                        file=files, **tc)
                res_text = res.text
                allure.attach(res_text, '接口响应信息', allure.attachment_type.TEXT)
                status_code = res.status_code
                allure.attach(self.allure_attach_response(res.json()), '接口响应信息', allure.attachment_type.TEXT)

                try:
                    res_json = json.loads(res_text)
                    if extract is not None:
                        self.extract_data(extract, res_text)
                    if extract_lst is not None:
                        self.extract_data_list(extract_lst, res_text)
                    # 处理断言
                    assert_res.assert_result(validation, res_json, status_code)
                except JSONDecodeError as js:
                    logs.error("系统异常或接口未请求！")
                    raise js
                except Exception as e:
                    logs.error(str(traceback.format_exc()))
                    raise e
        except Exception as e:
            logs.error(e)
            raise e

    @classmethod
    def allure_attach_response(cls, response):
        if isinstance(response, dict):
            allure_response = json.dumps(response, ensure_ascii=False, indent=4)
        else:
            allure_response = response
        return allure_response

    def extract_data(self, testcase_extract, response):
        """
        提取接口的返回参数，支持正则表达式和json提取，提取单个参数
        :param testcase_extract: testcase文件yaml中的extract值
        :param response: 接口的实际返回值,str类型
        :return:
        """
        pattern_lst = ['(.+?)', '(.*?)', r'(\d+)', r'(\d*)']
        try:
            for key, value in testcase_extract.items():
                for pat in pattern_lst:
                    if pat in value:
                        ext_list = re.search(value, response)
                        if pat in [r'(\d+)', r'(\d*)']:
                            extract_date = {key: int(ext_list.group(1))}
                        else:
                            extract_date = {key: ext_list.group(1)}
                        logs.info('正则提取到的参数：%s' % extract_date)
                        self.read.write_yaml_data(extract_date)
                if "$" in value:
                    ext_json = jsonpath.jsonpath(json.loads(response), value)[0]
                    if ext_json:
                        extract_date = {key: ext_json}
                    else:
                        extract_date = {key: "未提取到数据，该接口返回结果可能为空"}
                    logs.info('json提取到参数：%s' % extract_date)
                    self.read.write_yaml_data(extract_date)
        except:
            logs.error('接口返回值提取异常，请检查yaml文件extract表达式是否正确！')

    def extract_data_list(self, testcase_extract_list, response):
        """
        示例见末尾
        提取多个参数，支持正则表达式和json提取，提取结果以列表形式返回
        :param testcase_extract_list: yaml文件中的extract_list信息
        :param response: 接口的实际返回值,str类型
        :return:
        """
        try:  # testcase_extract_list： {'goodsIds': '$.goodsList[*].goodsId'}
            for key, value in testcase_extract_list.items():
                if "(.+?)" in value or "(.*?)" in value:
                    ext_list = re.findall(value, response, re.S)
                    if ext_list:
                        extract_date = {key: ext_list}
                        logs.info('正则提取到的参数：%s' % extract_date)
                        self.read.write_yaml_data(extract_date)
                if "$" in value:
                    # 增加提取判断，有些返回结果为空提取不到，给一个默认值
                    ext_json = jsonpath.jsonpath(json.loads(response), value)
                    if ext_json:
                        extract_date = {key: ext_json}
                    else:
                        extract_date = {key: "未提取到数据，该接口返回结果可能为空"}
                    logs.info('json提取到参数：%s' % extract_date)
                    self.read.write_yaml_data(extract_date)
        except:
            logs.error('接口返回值提取异常，请检查yaml文件extract_list表达式是否正确！')

from common.readyaml import ReadYamlData, get_testcase_yaml
if __name__ == '__main__':
    for case_info in get_testcase_yaml('../testcase/Business interface/BusinessScenario.yml'):
        RequestBase().specification_yaml(case_info)

"""
{'goodsIds': '$.goodsList[*].goodsId'}
{'goodsIds': ['18382788819', '33809635011', '56996760797', '82193785267', '74190550836']}
"goodsList": [
    {
      "goodsId": "18382788819",
      "goods_count": "233",
      "goods_image": "https://omsproductionimg.yangkeduo.com/images/2017-12-12/bcf848aa71c6389607ae7a84b70f1543.jpeg",
      "goods_name": "\u30102\u4ef6\u5957\u3011\u5957\u88c5\u79cb\u51ac\u65b0\u6b3e\u4eff\u736d\u5154\u6bdb\u9489\u73e0\u76ae\u8349\u6bdb\u6bdb\u77ed\u5916\u5957\u52a0\u539a\u5927\u8863\u5973\u88c5",
      "original_price": "",
      "unit_price": "\uffe599.00"
    },
    {
      "goodsId": "33809635011",
      "goods_count": "521",
      "goods_image": "https://omsproductionimg.yangkeduo.com/images/2017-12-12/176019babfdecffa1d9f98f40b7e99b4.jpeg",
      "goods_name": "\u597d\u5947\u5c0f\u68ee\u6797\u5fc3\u94bb\u88c5\u7eb8\u5c3f\u88e4M22\u62c9\u62c9\u88e4L18/XL14\u8d85\u8584\u900f\u6c14\u88e4\u578b\u5c3f\u4e0d\u6e7f 1\u4ef6\u88c5",
      "original_price": "",
      "unit_price": "\uffe5108.00"
    },
    {
      "goodsId": "56996760797",
      "goods_count": "1181",
      "goods_image": "https://omsproductionimg.yangkeduo.com/images/2017-12-12/efb5db42397550bffd3211ca6f197498.jpeg",
      "goods_name": "\u51bb\u5e72\u9e21\u5c0f\u80f8\u6574\u5757\u589e\u80a5\u8425\u517b\u53d1\u816e\u72d7\u72d7\u96f6\u98df\u65b0\u624b\u517b\u732b\u96f6\u98df\u5e7c\u732b\u96f6\u98df100g",
      "original_price": "",
      "unit_price": "\uffe517.80"
    },
    {
      "goodsId": "82193785267",
      "goods_count": "3000+",
      "goods_image": "https://omsproductionimg.yangkeduo.com/images/2017-12-12/efb5db42397550bffd3211ca6f197498.jpeg",
      "goods_name": "\u3010\u81ea\u8425\u3011ISB\u4f0a\u73ca\u5a1c\u610f\u5927\u5229\u6c34\u679c\u7cfb\u5217\u5ba0\u7269\u72ac\u732b\u6c90\u6d74\u9732\u9664\u81ed\u9999\u6ce2\u62a4\u6bdb\u7d20",
      "original_price": "",
      "unit_price": "\uffe5650.00"
    },
    {
      "goodsId": "74190550836",
      "goods_count": "1000+",
      "goods_image": "https://omsproductionimg.yangkeduo.com/images/2017-12-12/efb5db42397550bffd3211ca6f197498.jpeg",
      "goods_name": "\u3010\u65b0\u54c1\u96f60CM\u5d4c\u5165\u5f0f\u3011\u6d77\u5c14\u7535\u51b0\u7bb1410L\u5bb6\u7528\u6cd5\u5f0f\u56db\u95e8\u591a\u95e8\u5b98\u65b9\u6b63\u54c1",
      "original_price": "",
      "unit_price": "\uffe55746.00"
    }
  ],
"""