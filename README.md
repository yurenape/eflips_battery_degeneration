[![Tests](https://github.com/mpm-tu-berlin/eflips-depot/actions/workflows/unittests.yml/badge.svg)](https://github.com/mpm-tu-berlin/eflips-depot/actions/workflows/unittests.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# eflips-depot extension: Battery degeneration

This repository expands a simulation and planning tool [eflips-depot](https://github.com/mpm-tu-berlin/eflips-depot) which is the result of a research project of the Department of Methods of Product Development and
Mechatronics at the Technische Universität Berlin (see https://www.tu.berlin/mpm/forschung/projekte/eflips).
An installation guide for the original program for Ubuntu is found [here](https://tubcloud.tu-berlin.de/s/BJBH7jjM4pQWn7e).

This extension expands the model to consider the battery degeneration of the bus fleet and simulates it for a period of 12 years and visualizes the average degeneration of the fleet.
It also creates a steady state scenario based on the averave age of each vehicle type and depot. Based on that it integrates an age-based categorization system to optimize the assignment of the rotations.

To run the extension, you can instert the files in this repository into your bin folder within the eflips-depot repository.
Run the files in the following order:
yurena_example.py
yurena_steadystate.py
yurena_results.py

For this, they have to access a database and get input a scenario ID. The video tutorial exemplifies how to do that in PyCharm.
The database used to develop this program can be found [here](https://tubcloud.tu-berlin.de/s/BJBH7jjM4pQWn7e). It simulates one week of the fleet operation
If there is another database inserted, the results may vary in the duration of the simulated scenario. Please check the yurena_example file for that.

