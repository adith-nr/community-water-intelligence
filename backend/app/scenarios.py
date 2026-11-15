"""Fictional context for the two seeded incident scenarios."""
from datetime import timedelta

SCENARIOS = {
    ("demo-east", "discolouration", "municipal"): {
        "station": "Sangam scenario station",
        "turbidity": 31,
        "baseline": 8,
        "rain": (3, 18, 42),
        "interpretation": "In this scenario, rain and elevated river turbidity occurred around the same time. Runoff is one possible explanation for the river reading. Household sampling and a verified supply connection would be needed to assess the tap reports.",
    },
    ("demo-north", "odour", "borewell"): {
        "station": "Rasoolabad scenario station",
        "turbidity": 7,
        "baseline": 6,
        "rain": (0, 1, 0),
        "interpretation": "In this scenario, little rain and a small change in river turbidity give little reason to prioritize runoff. A shared borewell, storage or plumbing check is more relevant to the reported odour.",
    },
}


def scenario_context(incident, reports, latest):
    key = (incident.locality_id, incident.category, incident.source)
    scenario = SCENARIOS.get(key)
    if not scenario or not any(report.description.startswith(("Simulated report: ", "Demo fixture: ")) for report in reports):
        return [], None
    date = latest.date()
    rain = [
        {"label": (date - timedelta(days=2 - index)).isoformat(), "value": amount, "unit": "mm"}
        for index, amount in enumerate(scenario["rain"])
    ]
    river = [
        {"label": "Earlier sample", "value": scenario["baseline"], "unit": "NTU"},
        {"label": "Incident-day sample", "value": scenario["turbidity"], "unit": "NTU"},
    ]
    limitation = "Fictional values for this incident scenario. Household supply connection is unknown."
    return [
        {"id": "scenario-river", "kind": "river observation", "title": scenario["station"],
         "date": date.isoformat(), "simulated": True, "measurements": river,
         "excerpt": f"Simulated river turbidity moved from {scenario['baseline']} to {scenario['turbidity']} NTU.",
         "limitation": limitation},
        {"id": "scenario-rain", "kind": "weather", "title": "Rainfall around the incident",
         "date": date.isoformat(), "simulated": True, "measurements": rain,
         "excerpt": f"Simulated three-day rainfall totaled {sum(scenario['rain'])} mm.",
         "limitation": limitation},
    ], scenario["interpretation"]
