from distutils.core import setup, Extension

pkg = 'Extensions.TelekomSport'
setup (name = 'enigma2-plugin-extensions-telekomsport',
       version = '1.0',
       license='GPLv2',
       url='https://github.com/E2OpenPlugins',
       description='Telekom Sport Plugin',
       long_description='Plugin for watching Telekom Sport streams',
       author='betacentauri',
       author_email='betacentauri@arcor.de',
       packages = [pkg],
       package_dir = {pkg: 'plugin'},
       package_data={pkg: ['*.png']}
)
