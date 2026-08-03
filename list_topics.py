from rosbags.highlevel import AnyReader
from pathlib import Path
from rosbags.typesys import Stores, get_typestore

def list_topics(bag_path):
    typestore = get_typestore(Stores.LATEST)
    with AnyReader([Path(bag_path)], default_typestore=typestore) as reader:
        with open('topics_detailed.txt', 'w') as f:
            for t, m in reader.topics.items():
                f.write(f"{t}: {m.msgtype}\n")
    print("Topics written to topics_detailed.txt")

if __name__ == "__main__":
    list_topics('rosbag2_2025_12_01-16_59_00_0-001.db3')
