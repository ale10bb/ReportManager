import unittest
import os
import sys
from RM.archive import Archive
import tempfile


class TestArchive(unittest.TestCase):
    def test_init_nobin(self):
        with self.assertRaises(FileNotFoundError):
            if sys.platform == 'win32':
                archive = Archive(bin_path={
                    'winrar': 'C:\\fake.exe',
                })
            else:
                archive = Archive(bin_path={
                    'rar': 'fake_rar',
                    'unrar': 'fake_unrar',
                    'unar': 'fake_unar',
                })

    def test_init_defaultbin(self):
        with self.assertLogs('', level='INFO') as cm:
            archive = Archive()
        if sys.platform == 'win32':
            self.assertIn(
                'INFO:RM.archive:Archive configration (win32 -> WinRAR) confirmed.', cm.output)
        else:
            self.assertIn(
                'INFO:RM.archive:Archive configration (Linux -> rar/unrar/unar) confirmed.', cm.output)

    def test_init_pass(self):
        with self.assertLogs('', level='INFO') as cm:
            archive = Archive(password='testpass')
        self.assertIn('INFO:RM.archive:Archive password set.', cm.output)

    def test_init_wrongpass(self):
        with self.assertRaises(TypeError):
            archive = Archive(password=['wrongtype'])

    def test_archive_wrongsource(self):
        archive = Archive()
        with self.assertRaises(FileNotFoundError):
            archive.archive('fakepath', '1.rar')

    def test_archive_and_extract(self):
        archive = Archive()
        with tempfile.TemporaryDirectory() as work_path:
            with open(os.path.join(work_path, 'test.txt'), 'w') as fp:
                fp.write('testtest')
            self.assertTrue(archive.archive(
                work_path, os.path.join(work_path, 'test.rar')))
            os.remove(os.path.join(work_path, 'test.txt'))
            archive.extract(work_path, os.path.join(work_path, 'test.rar'))
            with open(os.path.join(work_path, 'test.txt')) as fp:
                self.assertEqual(fp.read(), 'testtest')

    def test_archive_and_extract_pass(self):
        archive = Archive(password='testpass')
        with tempfile.TemporaryDirectory() as work_path:
            with open(os.path.join(work_path, 'test.txt'), 'w') as fp:
                fp.write('testtest')
            self.assertTrue(archive.archive(
                work_path, os.path.join(work_path, 'test.rar')))
            os.remove(os.path.join(work_path, 'test.txt'))
            archive.extract(work_path, os.path.join(work_path, 'test.rar'))
            with open(os.path.join(work_path, 'test.txt')) as fp:
                self.assertEqual(fp.read(), 'testtest')

    def test_archive_and_extract_wrongpass(self):
        a = Archive(password='archivepass')
        e = Archive(password='extractpass')
        with tempfile.TemporaryDirectory() as work_path:
            with open(os.path.join(work_path, 'test.txt'), 'w') as fp:
                fp.write('testtest')
            self.assertTrue(a.archive(
                work_path, os.path.join(work_path, 'test.rar')))
            os.remove(os.path.join(work_path, 'test.txt'))
            self.assertFalse(
                e.extract(work_path, os.path.join(work_path, 'test.rar')))


if __name__ == '__main__':
    unittest.main()
