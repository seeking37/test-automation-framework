import allure
import pytest

from common.readyaml import get_testcase_yaml
from base.apiutil import RequestBase
from base.generateId import m_id, c_id


@allure.feature(next(m_id) + '登录功能')
class TestUserManager:

    # 场景，allure报告的目录结构
    @allure.story(next(c_id) + "用户登录")
    # 测试用例执行顺序设置
    @pytest.mark.run(order=1)
    # 参数化，yaml数据驱动
    @pytest.mark.parametrize('base_info,testcase', get_testcase_yaml("./loginUser.yaml"))
    def test_add_user(self, base_info, testcase):
        # verify_code = get_testcase_yaml("./verifyCode.yaml")
        # RequestBase().specification_yaml(verify_code[0][0], verify_code[0][1])
        allure.dynamic.title(testcase['case_name'])
        RequestBase().specification_yaml(base_info, testcase)
