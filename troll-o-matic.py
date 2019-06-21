#!/usr/bin/env python3

from reviewer import Reviewer
from gerrit import Gerrit, GerritRevision, GerritMessage
from configchecker import KernelConfigChecker

from trollreview import ReviewType
from trollreviewerfromgit import FromgitChangeReviewer
from trollreviewerupstream import UpstreamChangeReviewer
from trollreviewerfromlist import FromlistChangeReviewer
from trollreviewerchromium import ChromiumChangeReviewer

import argparse
import datetime
import json
import requests
import sys
import time

class Troll(object):
  def __init__(self, url, args):
    self.url = url
    self.args = args
    self.gerrit = Gerrit(url)
    self.tag = 'autogenerated:review-o-matic'
    self.blacklist = {}
    self.stats = { str(ReviewType.SUCCESS): 0, str(ReviewType.BACKPORT): 0,
                   str(ReviewType.ALTERED_UPSTREAM): 0,
                   str(ReviewType.MISSING_FIELDS): 0,
                   str(ReviewType.MISSING_HASH): 0,
                   str(ReviewType.INVALID_HASH): 0,
                   str(ReviewType.MISSING_AM): 0,
                   str(ReviewType.INCORRECT_PREFIX): 0,
                   str(ReviewType.FIXES_REF): 0,
                   str(ReviewType.KCONFIG_CHANGE): 0 }

  def inc_stat(self, review_type):
    if self.args.dry_run:
      return
    key = str(review_type)
    if not self.stats.get(key):
      self.stats[key] = 1
    else:
      self.stats[key] += 1

  def do_review(self, change, review):
    print('Review for change: {}'.format(change.url()))
    print('  Issues: {}, Feedback: {}, Vote:{}, Notify:{}'.format(
        review.issues.keys(), review.feedback.keys(), review.vote,
        review.notify))

    if review.dry_run:
      print(review.generate_review_message())
      print('------')
      return

    for i in review.issues:
      self.inc_stat(i)
    for f in review.feedback:
      self.inc_stat(f)
    self.gerrit.review(change, self.tag, review.generate_review_message(),
                       review.notify, vote_code_review=review.vote)

  def get_changes(self, prefix):
    message = '{}:'.format(prefix)
    after = datetime.date.today() - datetime.timedelta(days=5)
    changes = self.gerrit.query_changes(status='open', message=message,
                    after=after, project='chromiumos/third_party/kernel')
    return changes

  def add_change_to_blacklist(self, change):
    self.blacklist[change.number] = change.current_revision.number

  def is_change_in_blacklist(self, change):
    return self.blacklist.get(change.number) == change.current_revision.number

  def process_changes(self, changes):
    rev = Reviewer(git_dir=self.args.git_dir, verbose=self.args.verbose,
                   chatty=self.args.chatty)
    ret = 0
    for c in changes:
      if self.args.verbose:
        print('Processing change {}'.format(c.url()))

      # Blacklist if we've already reviewed this revision
      for m in c.messages:
        if m.tag == self.tag and m.revision_num == c.current_revision.number:
          self.add_change_to_blacklist(c)

      # Find a reviewer and blacklist if not found
      reviewer = None
      if FromlistChangeReviewer.can_review_change(c):
        reviewer = FromlistChangeReviewer(rev, c, self.args.dry_run)
      elif FromgitChangeReviewer.can_review_change(c):
        reviewer = FromgitChangeReviewer(rev, c, self.args.dry_run)
      elif UpstreamChangeReviewer.can_review_change(c):
        reviewer = UpstreamChangeReviewer(rev, c, self.args.dry_run)
      elif self.args.kconfig_hound and \
          ChromiumChangeReviewer.can_review_change(c):
        reviewer = ChromiumChangeReviewer(rev, c, self.args.dry_run,
                                          self.args.verbose)
      if not reviewer:
        self.add_change_to_blacklist(c)
        continue

      force_review = self.args.force_cl or self.args.force_all
      if not force_review and self.is_change_in_blacklist(c):
        continue

      result = reviewer.review_patch()
      if result:
        self.do_review(c, result)
        ret += 1

      self.add_change_to_blacklist(c)

    return ret

  def update_stats(self):
    if not self.args.dry_run and self.args.stats_file:
      with open(self.args.stats_file, 'wt') as f:
        json.dump(self.stats, f)
    print('--')
    summary = '  Summary: '
    total = 0
    for k,v in self.stats.items():
      summary += '{}={} '.format(k,v)
      total += v
    summary += 'total={}'.format(total)
    print(summary)
    print('')

  def run(self):
    if self.args.force_cl:
      c = self.gerrit.get_change(self.args.force_cl)
      print('Force reviewing change  {}'.format(c))
      self.process_changes([c])
      return

    if self.args.stats_file:
      try:
        with open(self.args.stats_file, 'rt') as f:
          self.stats = json.load(f)
      except FileNotFoundError:
        self.update_stats()

    prefixes = ['UPSTREAM', 'BACKPORT', 'FROMGIT', 'FROMLIST']
    if self.args.kconfig_hound:
      prefixes += ['CHROMIUM']

    while True:
      try:
        did_review = 0
        for p in prefixes:
          changes = self.get_changes(p)
          if self.args.verbose:
            print('{} changes for prefix {}'.format(len(changes), p))
          did_review += self.process_changes(changes)
        if did_review > 0:
          self.update_stats()
        if not self.args.daemon:
          break
        if self.args.verbose:
          print('Finished! Going to sleep until next run')

      except (requests.exceptions.HTTPError, OSError) as e:
        sys.stderr.write('Error getting changes: ({})\n'.format(str(e)))
        time.sleep(60)

      time.sleep(120)


def main():
  parser = argparse.ArgumentParser(description='Troll gerrit reviews')
  parser.add_argument('--git-dir', default=None, help='Path to git directory')
  parser.add_argument('--verbose', help='print commits', action='store_true')
  parser.add_argument('--chatty', help='print diffs', action='store_true')
  parser.add_argument('--daemon', action='store_true',
    help='Run in daemon mode, for continuous trolling')
  parser.add_argument('--dry-run', action='store_true', default=False,
                      help='skip the review step')
  parser.add_argument('--force-cl', default=None, help='Force review a CL')
  parser.add_argument('--force-all', action='store_true', default=False,
                      help='Force review all (implies dry-run)')
  parser.add_argument('--stats-file', default=None, help='Path to stats file')
  parser.add_argument('--kconfig-hound', default=None, action='store_true',
    help='Compute and post the total difference for kconfig changes')
  args = parser.parse_args()

  if args.force_all:
    args.dry_run = True

  troll = Troll('https://chromium-review.googlesource.com', args)
  troll.run()

if __name__ == '__main__':
  sys.exit(main())
