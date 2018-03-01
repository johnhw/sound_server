from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()
        
setup(name='sound_server',
      version='0.1.1',
      description='A Python-based sound server, allowing control of the OpenAL API via OSC messages.',
      long_description=readme(),
      url='http://github.com/johnhw/sound_server',
      keywords="sound OSC OpenAL server",
      author='John Williamson',
      author_email='johnhw@gmail.com',      
      license='MIT',
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Players',
        
        
      ],
      dependency_links=[],
      install_requires = ['numpy', 'pyopenal', 'pyogg'],
      packages=['sound_server'],
      zip_safe=False)