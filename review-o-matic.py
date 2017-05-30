  SIMILARITY = 'similarity index ([0-9]+)%'
  RENAME = 'rename (from|to) (.*)'
  ignore = [Type.CHUNK, Type.GITDIFF, Type.INDEX, Type.DELETED, Type.ADDED,
            Type.SIMILARITY, Type.RENAME]
      sys.stderr.write('ERROR: Could not classify line "%s"\n' % l)
  diff = difflib.unified_diff(remote, local, n=0)