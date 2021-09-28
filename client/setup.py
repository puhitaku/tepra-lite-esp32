from setuptools import setup, find_packages

__version__ = '1.0.0'
__author__ = 'Takumi Sueda'
__author_email__ = 'puhitaku@gmail.com'
__license__ = 'MIT License'
__classifiers__ = (
    'Development Status :: 4 - Beta',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
)

with open('README.md', 'r') as f:
    readme = f.read()

setup(
    name='tepracli',
    version=__version__,
    license=__license__,
    author=__author__,
    author_email=__author_email__,
    url='https://github.com/puhitaku/tepra-lite-esp32/tree/master/client',
    description='An example of tepra-lite-esp32 client / CLI',
    long_description=readme,
    long_description_content_type='text/markdown',
    classifiers=__classifiers__,
    packages=find_packages(),
    package_data={'': ['assets/ss3.ttf']},
    include_package_data=True,
    install_requires=['click', 'pillow', 'qrcode[pil]', 'requests'],
)
