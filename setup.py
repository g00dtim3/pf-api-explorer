# setup.py
from setuptools import setup, find_packages

setup(
    name='pf_api_explorer',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'streamlit',
        'pandas',
        'requests',
        'openpyxl'
    ],
    entry_points={
        'console_scripts': [
            'pf-api-explorer=pf_api_explorer.app:main'
        ]
    },
    author='Ton Nom',
    description='Explorateur Streamlit pour l\'API Ratings & Reviews',
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
