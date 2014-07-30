class AliPack:

  def __init__(self):
    pass

  def get_name(self):
    return 'VO_ALICE@' + self.software + '::' + self.version

  def from_string(self, s):
    '''Constructs the package definition from a string. String's format is the
       same as lines here: http://pcalienbuild4.cern.ch:8889/tarballs/Packages
    '''
    try:
      # remember to change it to None
      a = s.strip().split('\t', 5)

      self.tarballurl  = a[0]
      self.software    = a[1]
      self.version     = a[2]
      self.platform    = a[3]

      i2 = a[4].find()

      # TODO: check consistency
      self.packagename = a[4]

      if len(a) > 5:
        self._deps = a[5].split(',')
      else:
        self._deps = None

      i1 = self.tarballurl.find( self.platform )
      i2 = self.tarballurl.find( '.tar' )

      if i2 > i1:
        self.arch = self.tarballurl[i1:i2]
      else:
        self.arch = None

      #packdef['tarballurl'] = AliRootPacksBaseUrl + '/' + packdef['tarballurl']
      #packlist.append(packdef)

    except IndexError:
      raise AliPackError('Invalid string format for package definition: %s' % s)


class AliPackError(Exception):
  pass
