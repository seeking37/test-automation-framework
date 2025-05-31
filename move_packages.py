import os
import shutil

# 要移动的包列表
packages = ['base', 'demo', 'data', 'logs', 'conf', 'common', 'report', 'testcase', 'mock_server']

# 确保 src 目录存在
if not os.path.exists('src'):
    os.makedirs('src')

# 移动每个包
for package in packages:
    if os.path.exists(package):
        target = os.path.join('src', package)
        if os.path.exists(target):
            shutil.rmtree(target)
        shutil.move(package, target)
        print(f"Moved {package} to src/") 