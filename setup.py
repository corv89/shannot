from setuptools import setup

setup(name='sandboxlib',
      packages=['sandboxlib', 'sandboxlib.stubs'],
      setup_requires=["cffi"],
      cffi_modules=["sandboxlib/_commonstruct_build.py:ffibuilder"],
      install_requires=["cffi"],
      entry_points={
          'console_scripts': [
              'shannot=sandboxlib.cli:main',
          ],
      },
      )
