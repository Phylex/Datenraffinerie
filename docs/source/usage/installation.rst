Installation
============

PyPi
----

The Datenraffinerie is available on pypi. This means that it can be installed via pip. To be able to use the datenraffine Python 3.9 is needed. Python 2
is _not_ supported. It is recommended that a python virtual environment is used for installation. Python 3.9 can be installed on centos7 by compiling
from source. To set up a python environment run:
.. code-block:: bash

    python3.9 -m venv venv

this creates a `virtual environment <https://docs.python.org/3/library/venv.html>`. in the ``./venv`` directory. The virtual environment can be activated by running
.. code-block:: bash

    source ./venv/bin/activate

in a bash shell.
To deactivate the virtual environment, run:

.. code-block:: bash

    deactivate


In the virtual environment simply install the datenraffinerie via pip with the command

.. code-block:: bash

    pip install datenraffinerie

This will install the latest version released on the `python package index <https://pypi.org/project/datenraffinerie/>`.


from Source
-----------
To install the datenraffinerie it is assumed that python 3.9 is available and is executed via the ``python`` shell command.
To install the datenraffinerie from the git repository clone the repository and then change the working directory to the root of the git repository
then initialize a virtual environment as shown in `PyPi <PyPi>`. Then activate the virtual environment and run the command
.. code-block:: bash

    pip install .

This should install all needed runtime requirements for and datenraffinerie itself.
