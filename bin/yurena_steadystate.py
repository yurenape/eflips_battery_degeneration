import numpy as np
import math
import matplotlib.pyplot as plt
from collections import defaultdict
import json
import random
from dataclasses import replace
import copy

import psycopg2
from urllib.parse import urlparse, urlunparse

#! /usr/bin/env python3
import argparse
import os
import warnings

from eflips.model import *
from eflips.model import ConsistencyWarning
from sqlalchemy import create_engine, Column, Integer, update, text
from sqlalchemy.orm import Session

import eflips.depot.api
from bin.bar_plot_test import all_vehicletypes
#from yurena_example import years


from eflips.depot.api import (
    add_evaluation_to_database,
    delete_depots,
    init_simulation,
    insert_dummy_standby_departure_events,
    run_simulation,
    generate_realistic_depot_layout,
    simple_consumption_simulation,
    apply_even_smart_charging,
)


def list_scenarios(database_url: str):
    engine = create_engine(database_url, echo=False)
    with Session(engine) as session:
        scenarios = session.query(Scenario).all()
        for scenario in scenarios:
            rotation_count = (
                session.query(Rotation)
                .filter(Rotation.scenario_id == scenario.id)
                .count()
            )
            print(f"{scenario.id}: {scenario.name} with {rotation_count} rotations.")



#COPIED FROM CHATGPT ON 01.12. TITLE: Adding new attributes to ORM
def recreate_database_with_latest_data(original_db, copied_db, username, password, host="localhost"):
    """Ensure the copied database has the latest data by dropping and recreating it."""
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=username,
            password=password,
            host=host
        )
        conn.autocommit = True
        with conn.cursor() as cursor:
            # Terminate connections to the target database if it exists
            cursor.execute(
                f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = %s
                AND pid <> pg_backend_pid();
                """,
                (copied_db,)
            )
            # Drop the copied database if it exists
            cursor.execute(f"DROP DATABASE IF EXISTS {copied_db};")
            print(f"Dropped existing database: {copied_db}")

            # Terminate connections to the source database
            cursor.execute(
                f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = %s
                AND pid <> pg_backend_pid();
                """,
                (original_db,)
            )

            # Recreate the copied database from the source database
            cursor.execute(f"CREATE DATABASE {copied_db} WITH TEMPLATE {original_db} OWNER {username};")
            print(f"Database {copied_db} created successfully as a copy of {original_db}.")
    except psycopg2.Error as e:
        print(f"Error recreating the database: {e}")

#modify our argument to access the newly created steady state database
def modify_database_url(original_url, new_database_name):
    parsed_url = urlparse(original_url)
    new_path = f"/{new_database_name}"
    return urlunparse(parsed_url._replace(path=new_path))



if __name__ == "__main__":
    ###GIVEN CODE:      (pick scenario)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario_id",
        "--scenario-id",
        type=int,
        help="The id of the scenario to be simulated. Run with --list-scenarios to see all available scenarios.",
    )
    parser.add_argument(
        "--list_scenarios",
        "--list-scenarios",
        action="store_true",
        help="List all available scenarios.",
    )
    parser.add_argument(
        "--database_url",
        "--database-url",
        type=str,
        help="The url of the database to be used. If it is not specified, the environment variable DATABASE_URL is used.",
        required=False,
    )

    args = parser.parse_args()

    if args.database_url is None:
        if "DATABASE_URL" not in os.environ:
            raise ValueError(
                "The database url must be specified either as an argument or as the environment variable DATABASE_URL."
            )
        args.database_url = os.environ["DATABASE_URL"]

    if args.list_scenarios:
        list_scenarios(args.database_url)
        exit()

    if args.scenario_id is None:
        raise ValueError(
            "The scenario id must be specified. Use --list-scenarios to see all available scenarios, then run with "
            "--scenario-id <id>."
        )
    ###


    new_database_url = recreate_database_with_latest_data(
        original_db="eflips_oneweek",
        copied_db= f"eflips_steadystate_{args.scenario_id}",
        #specific to me!!! needs to be changed if someone else runs it todo: change that??
        username="yurenape",
        password="eflips",
        host="localhost"
    )

    new_database_url = modify_database_url(args.database_url, f"eflips_steadystate_{args.scenario_id}")

    engine = create_engine(new_database_url, echo=False)
    #engine = create_engine(args.database_url, echo=False)
    with Session(engine) as session:
        scenario = session.query(Scenario).filter(Scenario.id == args.scenario_id).one()
        assert isinstance(scenario, Scenario)


        #collect all classes_needed from Dataframe into dictionaries for easy access:
        classes_needed = ['VehicleType', 'Vehicle', 'Depot']
        for c in classes_needed:
            class_type = globals().get(c)   #converts String
            query_result = session.query(class_type).filter(class_type.scenario_id == scenario.id).all()
            globals()[f"all_{c.lower()}s"] = {x.id: x for x in query_result}      #e.g. dictionary is called all_vehicletypes, keys are vehicletype ids



        soh = np.load("soh_progression.npy")
        max_ages = np.load("max_ages.npy", allow_pickle=True)

        # create bar plot to show age distributions of vehicles in depot
        depot_indizes = {depot_id: i for i, depot_id in enumerate(all_depots.keys())}
        vehicle_type_indizes = {v_type_id: i for i, v_type_id in enumerate(all_vehicletypes.keys())}

        #import depot assignment dict with {vehicle_id: depot_id} from yurena_example file
        with open('veh_to_depot.json', 'r') as f:
            veh_to_depot = json.load(f)
        #convert keys back to int
        veh_to_depot = {int(k): int(v) for k, v in veh_to_depot.items()}

        vehicles_of_depot = defaultdict(list)
        # assign depots
        for vehicle_id, vehicle in all_vehicles.items():
            vehicle.depot_id = veh_to_depot[vehicle_id]  # Assign vehicles their depot_id from yurena_example
            vehicles_of_depot[vehicle.depot_id].append(vehicle)  # dict for easy access


        # todo: ausserhalb der Datenbank visualisieren, veh.age brauche ich nicht
        # create bar plot to show age distributions of vehicles in depot
        folder_path = os.path.join(os.getcwd(), f"steady_state_age_distributions_{scenario.id}")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Step 1: Calculate global y-axis limit and max x-axis range
        global_max_vehicles = 0
        global_max_age = 0
        for depot_id, depot in all_depots.items():
            for vt_id, vt in all_vehicletypes.items():
                #vehicles get replaced immediately uppon reaching max_age and are therefore not shown in steady state across the year
                max_age = max_ages[depot_indizes[depot_id], vehicle_type_indizes[vt_id]]
                if max_age:
                    agegroups = max_age - 1
                    num_veh = len([vehicle for vehicle in vehicles_of_depot[depot.id] if vehicle.vehicle_type_id == vt_id])
                    num_in_agegroup = num_veh // agegroups
                    remainder = num_veh % agegroups
                    age_distribution = [num_in_agegroup] * agegroups
                    for i in range(remainder):
                        age_distribution[i] += 1
                    global_max_vehicles = max(global_max_vehicles, max(age_distribution))
                    global_max_age = max(global_max_age, agegroups)

        # Variable to store legend handles and labels
        legend_handles = None
        legend_labels = None

        # Step 2: Create plots with consistent y-axis and x-axis settings
        for depot_id, depot in all_depots.items():
            depot_index = depot_indizes[depot_id]
            vehicles_in_depot = vehicles_of_depot[depot.id]
            bar_width = 0.3  # Adjusted bar width for multiple vehicle types
            x = np.arange(global_max_age)  # Global x range for consistent x-axis ticks

            # Create figure
            fig, ax = plt.subplots(figsize=(12, 8))
            plt.title(f"Age Distribution for {all_depots[depot.id].name}", fontsize = 28)

            pos = 0
            # Loop through each vehicle type to generate and save a histogram
            for vt_id, vt in all_vehicletypes.items():
                vt_index = vehicle_type_indizes[vt_id]
                max_age = max_ages[depot_indizes[depot_id], vehicle_type_indizes[vt_id]]
                if max_age:
                    agegroups = max_age - 1
                    veh_of_vt = [vehicle for vehicle in vehicles_in_depot if vehicle.vehicle_type_id == vt_id]
                    num_veh = len(veh_of_vt)

                    num_in_agegroup = num_veh // agegroups
                    remainder = num_veh % agegroups
                    age_distribution = [num_in_agegroup] * agegroups
                    for i in range(remainder):
                        age_distribution[i] += 1
                    x_positions = np.arange(agegroups)  # x positions for the current vehicle type
                    ax.bar(x_positions + pos, age_distribution, bar_width, label=vt.name)
                    pos += bar_width

            # Set consistent y-axis and x-axis limits
            ax.set_ylim(0, global_max_vehicles + 5)  # Consistent y-axis limit
            ax.set_xticks(x + (pos - bar_width) / 2)  # Center ticks
            ax.set_xticklabels([f"{i}" for i in range(global_max_age)], )  # Consistent x-axis labels
            ax.set_xlabel('Age in the Steady State [years]', fontsize=28)
            ax.set_ylabel('Number of vehicles [/]', fontsize=28)
            ax.tick_params(axis='both', which='major', labelsize=27)
            #ax.legend(title='Vehicle types', fontsize = 25,title_fontsize=22)

            # Save legend handles and labels for separate legend plot
            if legend_handles is None and legend_labels is None:
                legend_handles, legend_labels = ax.get_legend_handles_labels()

            plt.tight_layout()
            plt.savefig(os.path.join(folder_path, f'age_distribution_for_{depot.name}.png'))
            plt.close(fig)

        #print legend separately
        if legend_handles and legend_labels:  # Prüfen, ob Legendenelemente vorhanden sind
            fig, ax = plt.subplots(figsize=(6, len(legend_labels) * 1.2))  # Höhe proportional zur Anzahl der Einträge
            ax.axis('off')  # Achsen ausblenden
            legend = ax.legend(
                legend_handles,
                legend_labels,
                title='Vehicle types',
                fontsize=19,  # Schriftgröße der Einträge
                title_fontsize=20,  # Schriftgröße des Titels
                loc='center',  # Zentrierte Legende
                ncol=1,  # Einträge untereinander
                frameon=True,  # Rahmen um die Legende
                borderpad=1.5,  # Abstand innerhalb des Rahmens
            )
            plt.tight_layout()
            plt.savefig(os.path.join(folder_path, 'legend_only.png'))  # Legende als separate Datei speichern
            plt.close(fig)

        exit()

        # create helpful dict that references depots by station id instead of depot id:
        depot_station_ids = {depot.station_id: depot.id for depot in all_depots.values()}

        all_rotations = session.query(Rotation).filter(Rotation.scenario_id == scenario.id).all()
        all_trips = session.query(Trip).filter(Trip.scenario_id == scenario.id).all()
        all_routes = session.query(Route).filter(Route.scenario_id == scenario.id).all()

        #sort rotations by depot
        rotations_in_depot = defaultdict(list)

        #assign rotations to depots
        for rot in all_rotations:
            #checks all trips within rotation until a depot is found through route
            for i in range(len(rot.trips)):
                route = rot.trips[i].route
                dep_id = route.departure_station_id
                arr_id = route.arrival_station_id
                #checks if arrival or departure station is a depot. if so, assigns the rotation o depot and goes to next rotation
                if dep_id in depot_station_ids.keys():
                    depot_id = depot_station_ids[dep_id]
                    rotations_in_depot[depot_id].append(rot)
                    break
                elif arr_id in depot_station_ids.keys():
                    depot_id = depot_station_ids[arr_id]
                    rotations_in_depot[depot_id].append(rot)
                    break

        # This is the dictionary we will use to map from the "original" vehicle type to the "young" and "old"
        # vehicle types
        young_old_vts: dict[int, tuple[int, int]] = {} # Original ID maps to (young_id, old_id)
        for vt_id, vt in all_vehicletypes.items():
            vt_id: int # For PyCharm's autocomplete

            young_vt = VehicleType()
            for key, value in vars(vt).items():
                if key not in ["id", "_sa_instance_state"]:  # Exclude primary key and SQLAlchemy internal state
                    setattr(young_vt, key, value)
            # Overwrite specific attributes for "young"
            young_vt.name = f"{vt.name} (young)"
            young_vt.battery_capacity = vt.battery_capacity * 0.9
            young_vt.battery_capacity_reserve = vt.battery_capacity_reserve * 0.9

            # Create a new "old" vehicle type by copying attributes
            old_vt = VehicleType()
            for key, value in vars(vt).items():
                if key not in ["id", "_sa_instance_state"]:  # Exclude primary key and SQLAlchemy internal state
                    setattr(old_vt, key, value)
            # Overwrite specific attributes for "old"
            old_vt.name = f"{vt.name} (old)"
            old_vt.battery_capacity = vt.battery_capacity * 0.8
            old_vt.battery_capacity_reserve = vt.battery_capacity_reserve * 0.8

            session.add(young_vt)
            session.add(old_vt)
            session.flush()  # Assign ID to old_vt and young_vt
            young_old_vts[vt.id] = (young_vt.id, old_vt.id)
        #session.commit()

        #will save average duration of rotations of that vehicletype in that depot
        all_rotation_durs = {}

        #calculates the average duration of rotations in a depot for a certain vehicletype
        for depot_id, depot in all_depots.items():
            rots = rotations_in_depot[depot_id]
            for vt_id, vt in all_vehicletypes.items():
                #sorts for rotations with that vehicle id
                vt_rots = [rot for rot in rots if rot.vehicle_type_id == vt_id]
                rotation_durs = []
                if vt_rots:
                    #calculate avergage rotation duration
                    for rotation in vt_rots:
                        rot_duration = rotation.trips[-1].arrival_time - rotation.trips[0].departure_time
                        rotation_durs.append(rot_duration)
                    all_rotation_durs[depot_id, vt_id] = np.mean(rotation_durs)
                    #print(f"Depot: {depot_id}, VT: {vt_id}, {all_rotation_durs[depot_id, vt_id]}")

                    #assign rotations a new vehicletype_id based on if they are above or below average duration
                    #vt_if = 0 means young, vt_id = 1 means old
                    for rotation in vt_rots:
                        rot_duration = rotation.trips[-1].arrival_time - rotation.trips[0].departure_time
                        if rot_duration > all_rotation_durs[depot_id, vt_id]:
                            rotation.vehicle_type_id = young_old_vts[vt_id][0]   #young
                        else:
                            rotation.vehicle_type_id = young_old_vts[vt_id][1]   #old


        #copied from eflips example.py to reset and run simulation
        ##### Step 0: Clean up the database, remove results from previous runs #####
        # Delete all vehicles and events, also disconnect the vehicles from the rotations
        rotation_q = session.query(Rotation).filter(Rotation.scenario_id == scenario.id)

        rotation_q.update({"vehicle_id": None})
        session.query(Event).filter(Event.scenario_id == scenario.id).delete()
        session.query(Vehicle).filter(Vehicle.scenario_id == scenario.id).delete()

        #delete old vehicletypes for simulation
        #sollte nicht notwendig sein, da rotations neue VT haben
        for vt in all_vehicletypes.values():
            session.delete(vt)

        # Delete the old depot
        # This is a private API method automatically called by the generate_depot_layout method
        # It is run here explicitly for clarity.
        delete_depots(scenario, session)

        warnings.simplefilter("ignore", category=ConsistencyWarning)
        simple_consumption_simulation(scenario=scenario, initialize_vehicles=True)

        ##### Step 2: Generate the depot layout
        eflips.depot.api.generate_depot_layout(
            scenario=scenario, charging_power=300, delete_existing_depot=True
        )

        eflips.depot.api.simulate_scenario(scenario)

        session.commit()
    exit()

