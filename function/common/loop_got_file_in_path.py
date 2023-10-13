import os


def get_lableandwav(path, dir):
    all_path = []
    all_file = []
    dirs = os.listdir(path)
    print(
        dirs
    )
    for a in dirs:
        if os.path.isfile(path + "/" + a):
            all_path.append(dirs)
            if dir != "":
                all_file.append(dir)
        else:
            get_lableandwav(str(path) + "/" + str(a), a)

    return all_file, all_path


if __name__ == '__main__':
    def main():
        train_path = "./tool/"
        all_path, all_file = get_lableandwav(train_path, "")
        print(all_file)
        print("----------")
        print(all_path)
    main()