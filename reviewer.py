  MAX_CONTEXT = 5

  def __strip_kruft(self, diff, context):
              LineType.RENAME, LineType.EMPTY]
    ctx_counter = 0
        ctx_counter = 0
        continue

      if l_type == LineType.CONTEXT:
        if ctx_counter < context:
          ret.append(l)
        ctx_counter += 1
        continue

      ctx_counter = 0

      if l_type in ignore:
      else:
        sys.stderr.write('ERROR: line_type not handled {}: {}\n'.format(l_type,
                                                                        l))

  def find_fixes_reference(self, sha):
    cmd = self.git_cmd + ['log', '--format=oneline', '--abbrev-commit',
                          '--grep', 'Fixes: {}'.format(sha[:11]),
                          '{}..'.format(sha)]
    return subprocess.check_output(cmd).decode('UTF-8')

    cmd = self.git_cmd + ['show', '--minimal', '-U{}'.format(self.MAX_CONTEXT),
                          r'--format=%B', sha]
  def compare_diffs(self, a, b, context=0):
    if context > self.MAX_CONTEXT:
      raise ValueError('Invalid context given')

    a = self.__strip_commit_msg(a) or []
    b = self.__strip_commit_msg(b) or []
    a = self.__strip_kruft(a, context)
    b = self.__strip_kruft(b, context)