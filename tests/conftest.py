import pytest


@pytest.fixture
def hdb_api_response_generator():
    def _make(
        snapshot_count=1,
        data_count=2,
    ):
        responses = []

        for i in range(snapshot_count):
            carpark_data = []

            for j in range(data_count):
                carpark_data.append({
                    "update_datetime": (
                        f"2026-08-14T10:38:{(30 + i) % 60:02d}"
                    ),
                    "carpark_number": f"CP{j:04d}",
                    "carpark_info": [
                        {
                            "total_lots": "105",
                            "lot_type": "C",
                            "lots_available": str(30 + j + i),
                        }
                    ],
                })

            responses.append({
                "items": {
                    "timestamp": (
                        f"2026-08-14T10:38:{i % 60:02d}+08:00"
                    ),
                    "carpark_data": carpark_data
                }
            })

        return responses

    return _make


@pytest.fixture
def hdb_bronze_snapshot_generator():
    def _make(
        snapshot_count=1,
        data_count=2,
    ):
        snapshots = []

        for i in range(snapshot_count):
            values = []

            for j in range(data_count):
                values.append({
                    "carpark_info": [
                        {
                            "total_lots": "105",
                            "lot_type": "C",
                            "lots_available": str(30 + j + i),
                        }
                    ],
                    "carpark_number": f"CP{j:04d}",
                    "update_datetime": (
                        f"2026-08-11T16:58:{i % 60:02d}"
                    ),
                })

            snapshots.append({
                "timestamp": (
                    f"2026-08-11T09:00:{i % 60:02d}+00:00"
                ),
                "source": "hdb",
                "poll_start": "2026-08-11T09:00:12.173321+00:00",
                "poll_end": "2026-08-11T09:00:13.432756+00:00",
                "pages": 1,
                "records_count": data_count,
                "value": values
            })

        return snapshots

    return _make


@pytest.fixture
def lta_api_response_generator():
    def _make(
        snapshot_count=1,
        data_count=2,
    ):
        responses = []

        for i in range(snapshot_count):
            values = []

            for j in range(data_count):
                values.append({
                    "CarParkID": f"CP{j:04d}",
                    "Area": "",
                    "Development": f"BLK {j:04d}",
                    "Location": f"1.2937{j} 103.8571{j}",
                    "AvailableLots": 30 + j + i,
                    "LotType": "C",
                    "Agency": "HDB"
                })

            responses.append({
                "odata.metadata": (
                    "https://datamall2.mytransport.sg/"
                    "ltaodataservice/$metadata#CarParkAvailability"
                ),
                "value": values
            })

        return responses

    return _make


@pytest.fixture
def lta_bronze_snapshot_generator():
    def _make(
        snapshot_count=1,
        data_count=2,
    ):
        snapshots = []

        for i in range(snapshot_count):
            values = []

            for j in range(data_count):
                values.append({
                    "CarParkID": f"CP{j:04d}",
                    "Area": "",
                    "Development": f"BLK {j:04d}",
                    "Location": f"1.2937{j} 103.8571{j}",
                    "AvailableLots": 30 + j + i,
                    "LotType": "C",
                    "Agency": "HDB"
                })

            snapshots.append({
                "timestamp": (
                    f"2026-08-10T11:00:{i % 60:02d}+00:00"
                ),
                "source": "lta",
                "poll_start": "2026-08-10T11:00:07.245049+00:00",
                "poll_end": "2026-08-10T11:00:08.031497+00:00",
                "pages": 6,
                "records_count": data_count,
                "value": values
            })

        return snapshots

    return _make