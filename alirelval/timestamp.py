import calendar, datetime

class TimeStamp:

  '''Python handles dates like crazy. This class is constructed from a
     timestamp, holds a naive datetime and has methods with crystal clear
     names. Small but sufficient for our purposes.
  '''

  def __init__(self, ts_utc=None):
    if ts_utc is None:
      self._dt_utc = datetime.datetime.utcnow()
    else:
      self._dt_utc = datetime.datetime.utcfromtimestamp(ts_utc)

  def get_timestamp_usec_utc(self):
    return calendar.timegm( self._dt_utc.utctimetuple() ) + self._dt_utc.microsecond * 0.000001

  def get_datetime_naive_utc(self):
    return self._dt_utc

  def get_formatted_str(self, format):
    return self._dt_utc.strftime(format)

  def __str__(self):
    #return self._dt_utc.strftime('%Y-%m-%e %H:%M:%S')
    return str(self._dt_utc)

  def __sub__(self, other):
    '''Returns a timedelta object. Order: self-other. Get seconds with
       <timedelta>.total_seconds().
    '''
    return datetime.timedelta( seconds=self.get_timestamp_usec_utc()-other.get_timestamp_usec_utc() )

  @staticmethod
  def assert_unit_test():
    tsraw = 1406754375.6
    tsstr = '2014-07-30 21:06:15.600000'
    tsobj = TimeStamp(1406754375.6)
    assert tsobj.get_timestamp_usec_utc() == tsraw, 'UTC timestamps does not correspond'
    assert str(tsobj) == tsstr, 'UTC string representations do not correspond'
