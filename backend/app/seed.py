from sqlalchemy.dialects.postgresql import insert

from app.db import engine
from app.models import Locality, User

LOCALITIES = [
    dict(id="demo-east", name="Riverside pilot locality", city="Prayagraj",
         latitude=25.432, longitude=81.880, demo_data=True),
    dict(id="demo-north", name="North pilot locality", city="Prayagraj",
         latitude=25.470, longitude=81.854, demo_data=True),
]
USERS = [
    dict(id=f"resident-{index}", nickname=f"Resident {index}", role="resident",
         locality_id="demo-east", alert_opt_in=False, demo_data=True)
    for index in range(1, 4)
] + [
    dict(id="reviewer-1", nickname="Pilot reviewer", role="reviewer",
         locality_id="demo-north", alert_opt_in=False, demo_data=True),
]


def seed():
    with engine.begin() as connection:
        for model, rows in ((Locality, LOCALITIES), (User, USERS)):
            connection.execute(insert(model).values(rows).on_conflict_do_nothing(index_elements=["id"]))


if __name__ == "__main__":
    seed()

