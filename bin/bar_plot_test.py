import numpy as np
import os
import matplotlib.pyplot as plt
from collections import defaultdict
import random

# Simulated data for demonstration
class Depot:
    def __init__(self, depot_id, name):
        self.id = depot_id
        self.name = name

class VehicleType:
    def __init__(self, type_id, name):
        self.id = type_id
        self.name = name

class Vehicle:
    def __init__(self, vehicle_id, age, vehicle_type_id):
        self.id = vehicle_id
        self.age = age
        self.vehicle_type_id = vehicle_type_id

# Simulated depots and vehicle types
all_depots = {1: Depot(1, "Depot A"), 2: Depot(2, "Depot B")}
all_vehicletypes = {1: VehicleType(1, "Type X"), 2: VehicleType(2, "Type Y")}

# Simulated vehicle data
vehicles_of_depot = {
    1: [Vehicle(1, random.randint(0, 20), 1) for _ in range(50)] +
       [Vehicle(2, random.randint(0, 20), 2) for _ in range(40)],
    2: [Vehicle(3, random.randint(0, 20), 1) for _ in range(30)] +
       [Vehicle(4, random.randint(0, 20), 2) for _ in range(20)]
}



if __name__ == "__main__":


    # create bar plot to show age distributions of vehicles in depot
    folder_path = os.path.join(os.getcwd(), 'steady_state_age_distributions')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # visualize age distribution sorted by depots and vehicle types
    for depot in all_depots.values():
        vehicles_in_depot = vehicles_of_depot[depot.id]

        age_groups = range(0, 21)  # Age groups 0 to 20
        bar_width = 0.2  # Adjusted bar width for multiple vehicle types
        x = np.arange(len(age_groups))  # x positions for age groups

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))
        fig.suptitle(f'Distribution of Age in Depot: {depot.name}', fontsize=25)

        pos = 0
        # loop through each vehicle type to generate and save a histogram
        for vt_id, vt in all_vehicletypes.items():
            # Filter vehicles of vehicle type out of vehicles of that depot
            ages_data = [vehicle.age for vehicle in vehicles_in_depot if vehicle.vehicle_type_id == vt_id]
            v_type_name = all_vehicletypes[vt_id].name

            #Count occurrences of each age group
            age_distribution = [ages_data.count(age) for age in age_groups]

            # Create histogram for SoH distribution:
            ax.bar(x + pos, age_distribution, bar_width, label=vt.name)

            #move to next bar
            pos += bar_width

        ax.set_xlabel(f'Steady state ages')
        ax.set_xticks(x + int((pos - bar_width)/2))
        ax.set_ylabel('Number of Vehicles')

        ax.legend(title='Vehicle types')

        plt.tight_layout()
        plt.savefig(os.path.join(folder_path, f'test_age_distribution_for_{depot.name}.png'))
        plt.close(fig)