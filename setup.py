from distutils.core import setup

setup(
    name='inpassing-backend',
    version='0.1',
    packages=['inpassing', 'inpassing.tests', 'inpassing.worker'],
    url='https://github.com/lukesanantonio/inpassing-backend',
    license='MIT',
    author='Luke San Antonio Bialecki',
    author_email='lukesanantonio@gmail.com',
    description='A WIP flask web service powering a soon-to-be efficient, parking spot load-balancer thingy'
)
