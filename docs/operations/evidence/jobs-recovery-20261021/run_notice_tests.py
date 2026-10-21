from pathlib import Path
import socket,sys,unittest
root=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'backend'),str(root/'backend/tests'),str(root/'experiments/weather_autonomy')]
def blocked(*a,**kw):raise AssertionError('Network forbidden during offline tests')
socket.socket.connect=blocked
socket.create_connection=blocked
if __name__=='__main__':
 names=sorted(p.stem for p in (root/'backend/tests').glob('test_local_notice_*.py'))
 names+=['test_send_local_weather_notices_job','test_morning_forecast_delivery','test_evening_forecast_delivery']
 suite=unittest.TestLoader().loadTestsFromNames(names)
 result=unittest.TextTestRunner(verbosity=1).run(suite)
 raise SystemExit(not result.wasSuccessful())
