0.9.5 (2012-01-12)
==================

- Fixed media directory deletion bug [Simone Deponti]


0.9.4 (2012-01-03)
==================

- Fixed another bug with the copier when removing linked trees [Simone Deponti]


0.9.3 (2012-01-02)
==================

- Fixed bug with static directory copying [Simone Deponti]


0.9.2 (2011-12-23)
==================

- Added proper "smart" symlinking of static and origin [Simone Deponti]


0.9.1 (2011-12-13)
==================

- Fixed reST annoyance [Simone Deponti]


0.9 (2011-12-13)
================

- Added indentation preservation for initialization code. [Simone Deponti]

- Added a new default way to express databases [Simone Deponti]

- Added the ability to reference other sections. [Simone Deponti]

- Made 'settings.py' importable. [Simone Deponti]

- Sped up tests. [Simone Deponti]


0.8.1 (2011-09-22)
==================

- Fixed MANIFEST.in [Simone Deponti]


0.8 (2011-09-22)
================

- Refactored environment variables support [Simone Deponti]

- Added initialization support [Simone Deponti]

- Fixed documentation and added tests [Simone Deponti]


0.7.4 (2011-09-15)
==================

- Changed repository location [Simone Deponti]

- Made DEBUG explicit [Simone Deponti]

- Fixed paths on Windows [Dimitri Roche]


0.7.3 (2011-03-30)
==================

- Added environment-variables support [Mikko Ohtamaa]


0.7.2 (2010-11-18)
==================

- Fixed logging and added loglevel [Simone Deponti]


0.7.1 (2010-09-23)
==================

- Fixed multiple link bug [Simone Deponti]


0.7 (2010-09-23)
================

- Added ability to symlink the static origin [Simone Deponti]

- Refactored working set computation to achieve better
  performances [Simone Deponti]


0.6.1 (2010-07-22)
==================

- Fixed encoding bug. [Simone Deponti]


0.6 (2010-07-20)
================

- Added new mail settings, restructured defaults. [Simone Deponti]

- Added support for multiple databases and new-style database settings.
  [Simone Deponti]

- Fixed bugs in the tests and documentation. [Simone Deponti]


0.5.1 (2010-06-07)
==================

- Made the wsgi module more paster-compatible


0.5 (2010-06-03)
================

.. note:: This release is potentially backwards-incompatible: ``media-url`` and
          ``media-directory`` are now named ``static-url`` and
          ``static-directory`` respectively.

- Fixed MEDIA_URL mess [Simone Deponti]

- Added INTERNAL_IPS support [Simone Deponti]

- No defaults for middleware, template loaders and apps [Simone Deponti]


0.3.2 (2010-06-01)
==================

- Fixed WSGI support (uwsgi, custom loggers) [Simone Deponti]

- Fixed import bugs [Simone Deponti]

0.3.1 (2010-05-19)
==================

aka "Never release between midnight and 6am":

- Fixed absolute path bug for fixture dirs in default template [Simone Deponti]

- Fixed small template extension bug [Simone Deponti]

0.3 (2010-05-19)
================

- Added multiple media-origin support [Simone Deponti]

- Added fixture-dirs support [Simone Deponti]


0.2 (2010-05-17)
================

- First public release [Simone Deponti]

0.1 (2010-04-22)
================

- Created package [Simone Deponti]
