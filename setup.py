from setuptools import setup

setup(name='sandboxlib',
      packages=['sandboxlib', 'sandboxlib.stubs'],
      python_requires=">=3.11",
      entry_points={
          'console_scripts': [
              'shannot=sandboxlib.cli:main',
          ],
      },
      )
