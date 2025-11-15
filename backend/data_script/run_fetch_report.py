from item_fetch_conf import fetch_data, generate_excel, split_list

if __name__ == "__main__":
    # Fetch all DFIA entries
    data = fetch_data(split_list())
    generate_excel(data)

    # Uncomment below to test with just the first 10 entries
    # test_data = fetch_data(split_list()[:10])
    # generate_excel(test_data)
