import allure
import pytest

from base.apiutil import RequestBase
from common.readyaml import get_testcase_yaml


@pytest.mark.parametrize('base_info,testcase', get_testcase_yaml("./loginUser.yaml"))
def test_add_user(self, base_info, testcase):
    verify_code = get_testcase_yaml("./verifyCode.yaml")
    RequestBase().specification_yaml(verify_code[0][0], verify_code[0][1])
    allure.dynamic.title(testcase['case_name'])
    RequestBase().specification_yaml(base_info, testcase)


