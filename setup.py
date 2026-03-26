from setuptools import setup, find_packages

setup(
    name="flashsim",
    version="0.1.0",
    description="Flash video simulation pipeline",
    python_requires=">=3.12",
    packages=find_packages(exclude=["scripts", "tests"]),
    install_requires=[
        "torch>=2.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "ruff",
        ],
    },
)
