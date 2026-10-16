"""Read-only audit of the existing ADS sample. Does not publish weather data."""
import json
from pathlib import Path
import eccodes as ec
from uv_conversion import uv_index


def audit(path):
    rows = []
    with Path(path).open('rb') as stream:
        while (handle := ec.codes_grib_new_from_file(stream)) is not None:
            try:
                metadata = {key: ec.codes_get(handle, key) for key in (
                    'paramId', 'shortName', 'units', 'dataDate', 'dataTime',
                    'validityDate', 'validityTime', 'stepType', 'numberOfPoints')}
                if metadata['paramId'] != 214002 or metadata['shortName'] != 'uvbed' or metadata['stepType'] != 'instant':
                    raise ValueError('Unexpected UV parameter or accumulation')
                # ecCodes reports "~" for this sample. Keep that evidence visible;
                # conversion below is diagnostic, based on the documented parameter
                # semantics, NOT a generic acceptance of unknown units.
                point = ec.codes_grib_find_nearest(handle, 46.07, 13.23)[0]
                rows.append({**metadata, 'sample_location': 'Udine',
                             'grid_lat': point['lat'], 'grid_lon': point['lon'],
                             'grid_distance_km': point['distance'],
                             'raw_value': point['value'],
                             'diagnostic_uv_index': uv_index(point['value'], unit='W m-2')})
            finally:
                ec.codes_release(handle)
    if len(rows) != 24 or len({(r['validityDate'], r['validityTime']) for r in rows}) != 24:
        raise ValueError('Incomplete or duplicate sample hours')
    return {'status': 'diagnostic_only_not_published', 'hours': rows}


if __name__ == '__main__':
    print(json.dumps(audit(Path(__file__).parent / 'uv-pilot-local/source.grib'), indent=2))
