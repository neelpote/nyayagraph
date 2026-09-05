from .database import Base, engine
from . import models  # ensures model metadata is registered


def main() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()
