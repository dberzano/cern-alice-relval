import re

class Enum:

  '''Very simplistic implementation of an "enum".

     If you do:
       e = Enum( { 'a':1, 'b':2, 'c':3 } )
     then you can access keys as class members:
       > print e.a
       1
     and the other way around:
       > print e.getk(1)
       'a'

     Also supports a list instead of dict as argument: values are
     computed manually in that case.
  '''

  def __init__(self, kv):
    if isinstance(kv, list):
      self._invdict = {}
      count = 0
      for k in kv:
        if self._isnamevalid(k):
          setattr(self, k, count)
          self._invdict[count] = k
          count += 1
    elif isinstance(kv, dict):
      self._invdict = {}
      for k,v in kv.iteritems():
        if self._isnamevalid(k):
          setattr(self, k, v)
          self._invdict[v] = k
    else:
      raise EnumError('Enum takes list or dict as argument')

  def getk(self, val):
    return self._invdict[val]

  def getv(self, key):
    return getattr(self, key)

  def _isnamevalid(self, name):
    if re.search(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
      return True
    raise EnumError('invalid name: %s' % name)

  def __str__(self):
    return '<Enum %s>' % str(self._invdict)


class EnumError(Exception):
  pass
