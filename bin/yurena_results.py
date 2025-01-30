#! /usr/bin/env python3
import argparse
import os
import warnings

import numpy as np
import matplotlib.pyplot as plt

from eflips.model import *
from eflips.model import ConsistencyWarning
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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

    engine = create_engine(args.database_url, echo=False)
    with Session(engine) as session:
        scenario = session.query(Scenario).filter(Scenario.id == args.scenario_id).one()
        assert isinstance(scenario, Scenario)

        #todo: in Run configuration kann von eflips zu meinem steady state Modell gewechselt werden, um vorher nachher Vergleich zu machen
        """
        all_vehicletypes =  session.query(VehicleType).filter(VehicleType.scenario_id == scenario.id).all()
        all_vehicletypes_d = {x.id: x for x in all_vehicletypes}
        all_vehicles = session.query(Vehicle).filter(Vehicle.scenario_id == scenario.id).all()
        all_events = session.query(Event).filter(Event.scenario_id == scenario.id).all()
        all_events_by_vehicletype = {vt.id: [] for vt in all_vehicletypes}

        for event in all_events:
                all_events_by_vehicletype[event.vehicle_type_id].append(event)

        soc_min_vt = {}
        # Iterate over all events grouped by vehicle type ID
        for vt_id, events in all_events_by_vehicletype.items():
            #plt.hist([event.soc_end for event in events])
            #plt.show()
            if events:
                soc_min_vt[vt_id] = min(event.soc_end for event in events)
            else:
                soc_min_vt[vt_id] = None

        #Formel: minimale Kapazität (EoL with SoC_max = 0.8), die Fahrzeuge dieses VT brauchen, um alle Fahrten zu überwinden
        #bei Kategorisierungssystem -> SoC_min für alte Fahrzeuge sinkt? -> minimale Kapazität sinkt?
        #todo: battery_capacity_reserve??

        min_capacity_vt = {}
        for vt_id, vt in all_vehicletypes_d.items():
            if soc_min_vt[vt_id] is not None:
                min_capacity_vt[vt_id] = (1-soc_min_vt[vt_id]) * vt.battery_capacity
            else:
                min_capacity_vt[vt_id] = None

        #calculate capacity a purchase, include capacity reserve!
        capacity_vt = {}
        for vt_id, vt in all_vehicletypes_d.items():
            if "young" in all_vehicletypes_d[vt_id].name:
                capacity_vt[vt_id] = min_capacity_vt[vt_id] / 0.9
            elif "old" in all_vehicletypes_d[vt_id].name:
                capacity_vt[vt_id] = min_capacity_vt[vt_id]/0.8
            else:
                raise ValueError()

        #todo: bei fragmentierten VT in young/old Maximum nehmen
        print(f"Kleinster SoC für VT: {soc_min_vt}")
        print(f"Mindestkapazität für VT: {min_capacity_vt}")
        print(f"Initialkapazität für VT: {capacity_vt}")
        for vt_id in all_vehicletypes_d.keys():
            vehicles_of_vt = [vehicle for vehicle in all_vehicles if vehicle.vehicle_type_id == vt_id]
            print(f"Fahrzeuge für VT {vt_id}: {len(vehicles_of_vt)}")

        #vehicles_by_depot = session.query(Vehicle).join(Event).join(Depot).group_by(depot.name, VehicleType.id)
        """

        # Fahrzeugtypen und Daten aus der Tabelle
        fahrzeugtypen = ['EN', 'GN', 'DD']
        unangepasst = [497.91, 799.70, 465.68]  # Kapazität (unangepasst)
        angepasst = [458.30, 798.16, 465.68]  # Kapazität (angepasst)

        # unangepasst = [339, 714, 132] #Anzahl unangepasst
        # angepasst = [339, 714, 132] #Anzahl angepasst


        # Positionen und Balkenbreite
        x = np.arange(len(fahrzeugtypen))  # Position der Fahrzeugtypen
        bar_width = 0.35  # Breite der Balken

        # Diagramm erstellen
        fig, ax = plt.subplots(figsize=(8, 6))
        bars1 = ax.bar(x - bar_width / 2, unangepasst, bar_width, label='No categorization', color='skyblue')
        bars2 = ax.bar(x + bar_width / 2, angepasst, bar_width, label='With categorization', color='orange')

        # Titel, Achsen und Legende
        ax.set_xlabel('Vehicle type', fontsize=18)  # Vergrößert
        ax.set_ylabel('Initial capacity [kWh]', fontsize=18)  # Vergrößert
        ax.set_xticks(x)
        ax.set_xticklabels(fahrzeugtypen, fontsize=17)  # Vergrößert
        ax.tick_params(axis='y', labelsize=15.5)
        ax.legend(fontsize=13.5)  # Vergrößert

        # Werte über den Balken anzeigen
        for bars in [bars1, bars2]:
            for bar in bars:
                yval = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2, yval + 5, f'{yval}',
                        ha='center', va='bottom', fontsize=14.5)  # Vergrößert

        # Diagramm speichern und anzeigen
        plt.tight_layout()
        plt.savefig('balkendiagramm_kapazitaet.png', dpi=300)


        exit()