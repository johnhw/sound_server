from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()
        
setup(name='sound_server',
      version='0.1',
      description='A Python-based sound server, allowing control of the FModEx API via OSC messages.',
      long_description=readme(),
      url='http://github.com/johnhw/sound_server',
      keywords="sound OSC FModEx server",
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
      dependency_links=['https://github.com/tyrylu/pyfmodex/tarball/master#egg=pyfmodex',  'http://ixi-audio.net/content/download/SimpleOSC_0.3.2.zip#egg=SimpleOSC'],
      install_requires = ['numpy'],
      packages=['sound_server'],
      zip_safe=False)