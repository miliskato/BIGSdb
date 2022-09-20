import requests
import gzip

class CgMLSTProfilesDownloader:
    @staticmethod
    def download_cgmlst_profiles(download_link: str, save_name: str):
        r = requests.get(download_link, allow_redirects=True)
        if download_link.endswith('.gz'):
            open(save_name, 'wb').write(r.content)
        else:
            f = gzip.open(save_name, 'wb')
            f.write(r.content)
            f.close()

    @staticmethod
    def format_profile_gz(profile_file: str):
        with gzip.open(profile_file, 'r') as fin:
            file = fin.readlines()
            file[0] = "#" + file[0].decode("utf-8")
            for line in range(1,len(file)):
                file[line] = file[line].decode("utf-8").replace('N', '0')
        f = gzip.open(profile_file, 'wb')
        for line in file:
            f.write(bytes(line, 'utf-8'))
        f.close()

