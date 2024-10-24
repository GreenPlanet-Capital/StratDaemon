from setuptools import setup, find_packages

with open("requirements.txt", "r", encoding="utf-8") as f:
    REQUIRED_PACKAGES = f.read().splitlines()

# with open("requirements_dev.txt", "r", encoding="utf-8") as f:
#     EXTRA_PACKAGES = f.read().splitlines()

setup_args = dict(
    long_description_content_type="text/markdown",
    packages=find_packages(where='src'),
    install_requires=REQUIRED_PACKAGES,
)

if __name__ == '__main__':
    setup(**setup_args)
