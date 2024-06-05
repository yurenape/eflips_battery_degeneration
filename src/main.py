#!/usr/bin/env python3

"""
This is the main module of the project. It should contain the main entry point of the project. By
running this, the essential functionality of the project should be executed.
"""

from util import random_number

if __name__ == "__main__":
    print("Hello, world!")
    NUMBER = random_number()
    print(f"Here's a random number: {NUMBER}")
