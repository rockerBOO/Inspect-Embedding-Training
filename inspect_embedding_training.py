import copy
import os
import csv
import sys
import math
import torch
import getopt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from torch import Tensor

#os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

#######################################################################################################################
#                                                      CONFIG                                                         #
#######################################################################################################################
SAVE_LOSS_GRAPH_IMG: bool = True              # Create a .jpg of the Loss graph
SAVE_VECTOR_GRAPH_IMG: bool = True            # Create a .jpg of the Vector graphs

SHOW_PLOTS_AFTER_GENERATION: bool = False     # Show a popup with the Loss and Vector graphs after running this script

GRAPH_IMAGE_SIZE: tuple[int, int] = (19, 9)   # (X,Y) tuple in inches (multiply by 100 for (X,Y) pixel size for the output graphs)
GRAPH_SHOW_TITLE: bool = True                 # Adds the embed name at the top of the graphs

VECTOR_GRAPH_CREATE_FULL_GRAPH: bool = True           # Generates a vector graph with all vectors displayed
VECTOR_GRAPH_CREATE_LIMITED_GRAPH: bool = False       # Generates a vector graph with limited number of vectors displayed
VECTOR_GRAPH_LIMITED_GRAPH_NUM_VECTORS: int = 100     # Limits to this number of vectors drawn on the vector graph to this many lines. Normally there are 768 vectors per token.
VECTOR_GRAPH_SHOW_LEARNING_RATE: bool = True          # Adds the learning rate labels and vertical lines on the vector graphs

EXPORT_FOLDER_EMBEDDING_TABLE_TO: str = None               # Saves the table when using the --folder launch arg. If you get a ModuleNotFoundError: No module named 'openpyxl', then try running: pip install openpyxl     Valid values are: None, "xlsx", "csv", "html", "json"
#######################################################################################################################
#                                                    END CONFIG                                                       #
#######################################################################################################################


DIMS_PER_VECTOR = 768 # SD 1.5 has 768, 2.X has more
BASEDIR: str = os.path.realpath(os.path.dirname(__file__))   # the path where this .py file is located, ex "C:\Stable Diffusion\textual_inversion\2022-12-30\EmbedFolderName"
output_dir: str = BASEDIR    # where the output graph images are saved
working_dir: str = BASEDIR   # where we look for embeddings


def parse_args(argv) -> None:
    try:
        opts, args = getopt.getopt(argv[1:], "h", ["help", "dir=", "out=", "file=", "folder="])
    except getopt.GetoptError as e:
        sys.exit(e)

    for opt, arg in opts:
        #print(f"arg={arg}")
        if opt in ("-h", "--help"):
            print("Place this Python file in the textual inversion folder in the specific embedding folder you want to analyze (next to textual_inversion_loss.csv). Optionally, you can use the --dir \"/path/to/folder\" launch argument to specify the folder to use.")
            print("launch args:")
            print("--help -h")
            print("    This help message.")
            print("--dir")
            print("    The \"/path/to/embedding/folder\" to use instead of the local path where this script is at. This directory should have the textual_inversion_loss.csv file in it.")
            print("--out")
            print("    The \"/path/to/an/output/folder\" to use instead of the local path for outputting images.")
            sys.exit(0)
        # elif opt in ("-d", "--dir"):
        elif opt == "--dir":
            global working_dir
            working_dir = arg
            print(f"Directory set to: {working_dir}")
        elif opt == "--out":
            global output_dir
            output_dir = arg
            print(f"Output directory set to: {output_dir}")
        elif opt == "--file":
            embedding_file_name = arg
            inspect_embedding_file(embedding_file_name)
            sys.exit(0)
        elif opt == "--folder":
            embedding_folder_name = arg
            inspect_embedding_folder(embedding_folder_name)
            sys.exit(0)


def inspect_embedding_file(embedding_file_name: str) -> None:
    split_tup = os.path.splitext(embedding_file_name)
    file_name = split_tup[0]
    file_extension = split_tup[1]

    if file_extension == "":
        embedding_file_name = embedding_file_name + ".pt"   #fix user error, add file extension

    elif file_extension != ".pt":
        print(f"[ERROR] '{embedding_file_name}' is not a .pt file.")
        sys.exit(1)

    _, _, internal_name, step, sd_checkpoint_hash, sd_checkpoint_name, token, vectors_per_token, magnitude, strength = get_embedding_file_data(embedding_file_name)

    print(f"Data for embedding file: {embedding_file_name}")
    print(f"  Internal name: {internal_name}")
    print(f"  Model name it was trained on: {sd_checkpoint_name}")
    print(f"  Model hash it was trained on: {sd_checkpoint_hash}")
    print(f"  Token: {token}")
    print(f"  Vectors per token: {vectors_per_token}")
    print(f"  Total training steps: {step}")
    print(f"  Average vector strength: {round(strength, 4)}")
    print(f"  Average vector magnitude: {round(magnitude, 4)}")


def inspect_embedding_folder(embedding_folder_name: str, max_rows: int = 1000, sorted_column: int = 1) -> None:
    data = []
    i = 0
    final_embedding_file_name = ""
    try:
        for embedding_file_name in os.listdir(embedding_folder_name):  # "EmbedName-500.pt"
            if not embedding_file_name.endswith(".pt"):
                continue

            embed_path = os.path.join(embedding_folder_name, embedding_file_name)
            _, _, internal_name, step, sd_checkpoint_hash, sd_checkpoint_name, token, vectors_per_token, magnitude, strength = get_embedding_file_data(embed_path)

            #data[step] = [embedding_file_name, strength, magnitude]
            data.append([embedding_file_name, strength, magnitude])
            final_embedding_file_name = embedding_file_name
            i += 1
    except FileNotFoundError as e:
        print(f"[ERROR] Folder not found: {embedding_folder_name}.")
        sys.exit(e)

    if i == 0:
        print(f"[ERROR] No embedding .pt files found at: {embedding_folder_name}")
        return

    #print the table
    pd.options.display.max_rows = max_rows
    pd.options.display.float_format = "{:,.4f}".format
    data.sort(key=lambda x: x[sorted_column])
    df = pd.DataFrame(data, columns=["Embedding", "Strength", "Magnitude"])
    print(df)

    if EXPORT_FOLDER_EMBEDDING_TABLE_TO is not None:
        file_extension = EXPORT_FOLDER_EMBEDDING_TABLE_TO.lower()
        split_tup = os.path.splitext(final_embedding_file_name)
        file_name = split_tup[0]
        if file_extension == "xlsx":
            df.to_excel(f"{file_name}.{file_extension}", sheet_name=file_name, index=False, header=True)
        elif file_extension == "csv":
            df.to_csv(f"{file_name}.{file_extension}", index=False, header=True)
        elif file_extension == "html":
            df.to_html(f"{file_name}.{file_extension}", index=False, header=True)
        elif file_extension == "json":
            df.to_json(f"{file_name}.{file_extension}")

        #df.to_markdown(f"{file_name}.md", index=False, header=True)


def get_embedding_file_data(embedding_file_name: str) -> (dict[str, int], dict[str, Tensor], str, int, str, str, str, int, float, float):
    global DIMS_PER_VECTOR

    try:
        #embed = torch.load(embedding_file_name, map_location="cpu")
        embed = torch.load(embedding_file_name, map_location=torch.device("cpu"))

    except FileNotFoundError as e:
        print(f"[ERROR] Embedding file {embedding_file_name} not found.")
        sys.exit(e)

    vector_data = {}
    string_to_token = embed["string_to_token"]  #{'*': 265}
    string_to_param = embed["string_to_param"]  #{'*': tensor([[ 0.0178,  0.0123, -0.0003,  ...,  0.0420, -0.0379, -0.0294], [-0.0085, -0.0037,  0.0069,  ...,  0.0240, -0.0191,  0.0299], [ 0.0163, -0.0113,  0.0093,  ...,  0.0757,  0.0006, -0.0272]], requires_grad=True)}
    internal_name = embed["name"]               #EmbedTest
    step = embed["step"] + 1                    #1000
    sd_checkpoint_hash = embed["sd_checkpoint"] #a9263745
    sd_checkpoint_name = embed["sd_checkpoint_name"]    #v1-5-pruned
    token = list(string_to_token.keys())[0]  #"*"

    tensors = embed["string_to_param"][token]
    #step = embed["step"] + 1  # starts counting at 0, so add 1
    vector_data[step] = torch.flatten(tensors).tolist()
    magnitude = get_vector_data_magnitude(vector_data, step)
    strength = get_vector_data_strength(vector_data, step)
    vectors_per_token = int(len(vector_data[step]) / DIMS_PER_VECTOR)


    return string_to_token, string_to_param, internal_name, step, sd_checkpoint_hash, sd_checkpoint_name, token, vectors_per_token, magnitude, strength


def load_textual_inversion_loss_data_from_file() -> dict[int, dict[str, str]]:
    loss_csv_file = os.path.join(working_dir, "textual_inversion_loss.csv") # the default name created by Automatic1111
    if os.path.isfile(loss_csv_file):
        with open(loss_csv_file) as metadata_file:
            return {int(rec["step"]): rec for rec in csv.DictReader(metadata_file)}

    loss_csv_file = os.path.join(working_dir, "prompt_tuning_loss.csv") # alternate name created by DreamArtist
    if os.path.isfile(loss_csv_file):
        print(f"Found prompt_tuning_loss.csv, loading that instead of textual_inversion_loss.csv")
        with open(loss_csv_file) as metadata_file:
            return {int(rec["step"]): rec for rec in csv.DictReader(metadata_file)}

    print(f"[ERROR] Could not find file: textual_inversion_loss.csv")
    print("This error could happen if this script is set to use the wrong directory, or if not enough training steps have passed for the file to be created yet. In Automatic1111 Web UI, try lowering the value for the setting \"Save an csv containing the loss to log directory every N steps, 0 to disable\".")
    sys.exit()


def get_learn_rate_changes(textual_inversion_loss_data):
    learn_rate_changes = {}  # dict[index: int, (step: int, learn rate: float)]
    last_learn_rate = -1
    new_i = 0
    for step in textual_inversion_loss_data:
        new_learn_rate = textual_inversion_loss_data[step]["learn_rate"]
        # print(f"step {step} -> {new_learn_rate} learn rate")
        if last_learn_rate != new_learn_rate:
            learn_rate_changes[new_i] = (step, float(new_learn_rate))
            last_learn_rate = new_learn_rate

            print(f"Learning rate at step {step}: {learn_rate_changes[new_i][1]}")
            new_i += 1
    if len(learn_rate_changes) == 1:
        learn_rate_changes[0] = (0, learn_rate_changes[0][
            1])  # only 1 learning rate change, set starting step to 0. makes the Learn rate label centered
    return learn_rate_changes


def analyze_embedding_files(embedding_dir: str) -> (dict[int, Tensor], str, int, int):
    global DIMS_PER_VECTOR
    embed_name = None        # "EmbedName"
    number_of_embedding_files = 0
    highest_step = -1
    vector_data = {}
    num_skipped_neg_files = 0
    try:
        for embedding_file_name in os.listdir(embedding_dir):  # "EmbedName-500.pt"
            if not embedding_file_name.endswith(".pt"):
                continue

            if embedding_file_name.endswith("-neg.pt"):
                num_skipped_neg_files += 1
                continue

            embed_path = os.path.join(embedding_dir, embedding_file_name)
            embed = torch.load(embed_path, map_location="cpu")
            #tensors = embed["string_to_param"]["*"]
            #step = embed["step"] + 1  # starts counting at 0, so add 1
            #vector_data[step] = torch.flatten(tensors).tolist()
            #number_of_embedding_files += 1

            string_to_token, string_to_param, internal_name, step, sd_checkpoint_hash, sd_checkpoint_name, token, vectors_per_token, magnitude, strength = get_embedding_file_data(embed_path)
            tensors = embed["string_to_param"][token]
            vector_data[step] = torch.flatten(tensors).tolist()
            number_of_embedding_files += 1

            # print(f"step:{step}")

            if step > highest_step:
                highest_step = step  # + 1
                embed_name = embedding_file_name  # save the file name with the highest step count
                #vectors_per_token = int(len(vector_data[step]) / DIMS_PER_VECTOR)

            # print(f"Loaded data from embedding: {embed_file_name}")

    except FileNotFoundError as e:
        print("[ERROR] Make sure to place this Python file in the textual inversion folder in the specific embedding folder you want to analyze (next to textual_inversion_loss.csv). Optionally, you can use the --dir \"/path/to/embedding/folder\" launch argument to specify the folder to use.")
        sys.exit(e)

    vectors_per_token = int(len(vector_data[highest_step]) / DIMS_PER_VECTOR)
    embed_name = embed_name.replace(".pt", "")[:-(len(str(highest_step)) + 1)]  # "EmbedName", trim "-XX.pt" off the end
    print(f"This embedding has {vectors_per_token} vectors per token.")
    print(f"Loaded {number_of_embedding_files} embedding files up to training step {highest_step}.")

    if num_skipped_neg_files > 0:
        # DreamArtist extension creates a "EmbedName-XXXX-neg.pt" file along with the usual "EmbedName-XXXX.pt" file, so we ignore the "-neg.pt" files
        print(f"Skipped {num_skipped_neg_files} files that ended with \"-neg.pt\"")

    return tensors, vector_data, embed_name, highest_step, number_of_embedding_files


def create_loss_plot(title: str, data: dict, save_img: bool, output_file_name: str) -> None:
    plt.figure(figsize=GRAPH_IMAGE_SIZE)
    loss = pd.DataFrame(data).T.sort_index()["loss"].astype(float).loc[1:]
    #loss = pd.DataFrame(data).T.sort_index()["loss"].astype(float).iloc[1:]    # don't know what the difference is between loc and iloc, both work.
    # print("loss:")
    # print(loss)

    # x: step, y: loss
    plt.scatter(loss.index, loss, color=(0, 0, 0, 0.2))  # point values
    plt.plot(loss.rolling(window=5).mean(), color=(0, 0, 0, 0.4))  # best fit line over 5 steps
    plt.plot(loss.rolling(window=50).mean(), color=(0, 0, 0, 0.7))  # best fit line over 50 steps

    z1 = np.polyfit(loss.index, loss, 1)
    p1 = np.poly1d(z1)(loss.index)
    z2 = np.polyfit(loss.index, loss, 5)
    p2 = np.poly1d(z2)(loss.index)
    p3 = np.poly1d([0, z1[1]])(loss.index)
    
    plt.plot(p3, ":", color=(0, 0, 0, 0.5))
    plt.plot(p1, color=(1, 0, 1, 0.5))
    plt.plot(p2, color=(0, 1, 1, 0.5))

    min_y_value, max_y_value = plt.gca().get_ylim()
    min_x_value, max_x_value = plt.gca().get_xlim()

    if title is not None:
        x = (min_x_value + max_x_value) / 2
        y = (max_y_value - min_y_value) * 1.10 + min_y_value
        plt.text(x, y, title, fontsize="20", ha="center", va="center")

    if save_img:
        plt.savefig(output_dir + "/" + output_file_name)
        print(f"Created: {output_file_name}")


def create_vector_plot(title: str, data: dict[int, dict[int, Tensor]], learn_rate_changes: dict[int, (int, float)], highest_step: int, show_learning_rate: bool, save_img: bool, output_file_name: str, limit_num_vectors: int) -> None:

    # need to get the strength/magnitude BEFORE we truncate the data
    strength = get_vector_data_strength(data, highest_step)
    magnitude = get_vector_data_magnitude(data, highest_step)

    vectors_shown_text = None
    if 0 < limit_num_vectors < len(data[highest_step]):
        vectors_shown_text = f"{limit_num_vectors} of {len(data[highest_step])} vectors shown"

        # create a copy of the vector data so when we truncate it, it doesn't truncate the original reference
        data = copy.deepcopy(data)

        # truncate the vector data
        for step in data:
            data[step] = data[step][:VECTOR_GRAPH_LIMITED_GRAPH_NUM_VECTORS]

    plt.figure(figsize=GRAPH_IMAGE_SIZE)
    plt.plot(pd.DataFrame(data).T.sort_index())
    min_y_value, max_y_value = plt.gca().get_ylim()
    min_x_value, max_x_value = plt.gca().get_xlim()

    if show_learning_rate:
        # plot the Learn rate: XX labels and lines
        for i in learn_rate_changes:
            #print(f"i={i}, len(learn_rate_changes)={len(learn_rate_changes)}")
            step, learn_rate = learn_rate_changes[i]
            nextStep = highest_step
            if i < len(learn_rate_changes) - 1:
                nextStep = learn_rate_changes[i+1][0]

            #print(f"step={step}, nextStep={nextStep}")
            x = (step + nextStep) / 2
            y = (max_y_value - min_y_value) * 1.03 + min_y_value
            # if i % 2 == 1:
            #     y += (max_y_value - min_y_value) * 0.06
            #print(f"Learn rate: {learn_rate} at ({x},{y}), step={step}, nextStep={nextStep}")
            plt.text(x, y, f"Learn rate:\n{learn_rate}", fontsize="12", ha="center", va="center")    #Learn rate labels

            if len(learn_rate_changes) > 1: #create vertical line only if there is a learning rate change
                plt.axvline(step, color=(0, 0, 0, 0.4), linestyle="dotted")



    if vectors_shown_text is not None:
        x = (min_x_value + max_x_value) / 2
        y = min_y_value - (max_y_value - min_y_value) * 0.10
        plt.text(x, y, vectors_shown_text, fontsize="10", ha="center", va="center")

    if title is not None:
        x = (min_x_value + max_x_value) / 2
        y = (max_y_value - min_y_value) * 1.10 + min_y_value
        plt.text(x, y, title, fontsize="20", ha="center", va="center")

    x = (max_x_value - min_x_value) * 0.065 + max_x_value
    y = (max_y_value + min_y_value) / 2
    plt.text(x, y, f"Average vector strength:\n{round(strength, 4)}", fontsize="9", ha="center", va="center")

    x = (max_x_value - min_x_value) * 0.065 + max_x_value
    y = (max_y_value + min_y_value) / 2 - (max_y_value - min_y_value) * 0.1
    plt.text(x, y, f"Average vector magnitude:\n{round(magnitude, 4)}", fontsize="9", ha="center", va="center")

    if save_img:
        plt.savefig(output_dir + "/" + output_file_name)
        print(f"Created: {output_file_name}")

    print(f"  Average vector strength: {round(strength, 4)}")
    print(f"  Average vector magnitude: {round(magnitude, 4)}")


def get_vector_data_strength(data: dict[int, dict[int, Tensor]], step: int) -> float:
    value = 0
    for n in data[step]:
        value += abs(n)
    value = value / len(data[step]) # the average value of each vector (ignoring negative values)
    return value


def get_vector_data_magnitude(data: dict[int, dict[int, Tensor]], step: int) -> float:
    value = 0
    for n in data[step]:
        value += pow(n, 2)
    vectors_per_token = int(len(data[step]) / DIMS_PER_VECTOR)  # ie: 1, 3, 10, etc
    value = math.sqrt(value) / vectors_per_token
    return value


def main():

    parse_args(sys.argv)

    if not SAVE_LOSS_GRAPH_IMG and not SAVE_VECTOR_GRAPH_IMG and not SHOW_PLOTS_AFTER_GENERATION:
        print("[ERROR] Not set to create or show any plots. Change the global variables so that this script can do something.")
        sys.exit()


    embeddings_dir = os.path.join(working_dir, "embeddings")
    tensors, vector_data, embed_name, highest_step, number_of_embedding_files = analyze_embedding_files(embeddings_dir)
    #print(f"vector_data:")
    #print(vector_data)  # dict{step:[768xDimensions of floats]}
    #print(pd.DataFrame(vector_data).T.sort_index())  # massive amounts of numbers, [step][768 x Dimensions of floats]

    textual_inversion_loss_data = None  # this is loaded only if needed later on

    #print(f"learn_rate_changes: {learn_rate_changes}")
    print("Generating graphs...")

    if SAVE_LOSS_GRAPH_IMG or SHOW_PLOTS_AFTER_GENERATION:  # loss plot
        if textual_inversion_loss_data is None:
            textual_inversion_loss_data = load_textual_inversion_loss_data_from_file()
            #print(f"textual_inversion_loss_data:")
            #print(textual_inversion_loss_data)
            #print(pd.DataFrame(textual_inversion_loss_data).T.sort_index())   # the same format as the textual_inversion_loss.csv file

        create_loss_plot(title=embed_name if GRAPH_SHOW_TITLE else None,
                         data=textual_inversion_loss_data,
                         save_img=SAVE_LOSS_GRAPH_IMG,
                         output_file_name=f"{embed_name}-{highest_step}-loss.jpg")
    else:
        print("Skipping making a loss plot.")


    if number_of_embedding_files == 0:
        print(f"[ERROR] Could not find any embedding .pt files in {embeddings_dir}")
        sys.exit()
    elif number_of_embedding_files == 1:
        print("[WARNING] Only 1 embedding file found, the vector plot won't show any useful data.")


    if SAVE_VECTOR_GRAPH_IMG or SHOW_PLOTS_AFTER_GENERATION:  # vector plot

        learn_rate_changes = {}
        if VECTOR_GRAPH_SHOW_LEARNING_RATE:
            if textual_inversion_loss_data is None:
                textual_inversion_loss_data = load_textual_inversion_loss_data_from_file()
            learn_rate_changes = get_learn_rate_changes(textual_inversion_loss_data)

        if VECTOR_GRAPH_CREATE_FULL_GRAPH:

            create_vector_plot(title=embed_name if GRAPH_SHOW_TITLE else None,
                               data=vector_data,
                               learn_rate_changes=learn_rate_changes,
                               highest_step=highest_step,
                               show_learning_rate=VECTOR_GRAPH_SHOW_LEARNING_RATE,
                               save_img=SAVE_VECTOR_GRAPH_IMG,
                               output_file_name=f"{embed_name}-{highest_step}-vector.jpg",
                               limit_num_vectors=-1,
                               )


        if VECTOR_GRAPH_CREATE_LIMITED_GRAPH:

            if 0 < VECTOR_GRAPH_LIMITED_GRAPH_NUM_VECTORS < len(vector_data[highest_step]):

                create_vector_plot(title=embed_name if GRAPH_SHOW_TITLE else None,
                                   data=vector_data,
                                   #data=copied_vector_data,
                                   learn_rate_changes=learn_rate_changes,
                                   highest_step=highest_step,
                                   show_learning_rate=VECTOR_GRAPH_SHOW_LEARNING_RATE,
                                   save_img=SAVE_VECTOR_GRAPH_IMG,
                                   output_file_name=f"{embed_name}-{highest_step}-vector-({VECTOR_GRAPH_LIMITED_GRAPH_NUM_VECTORS}-vector-limit).jpg",
                                   limit_num_vectors=VECTOR_GRAPH_LIMITED_GRAPH_NUM_VECTORS,
                                   )
            else:
                print(f"[ERROR] VECTOR_GRAPH_LIMITED_GRAPH_NUM_VECTORS is set to {VECTOR_GRAPH_LIMITED_GRAPH_NUM_VECTORS}. It needs to be greater than 0, or less than {len(vector_data[highest_step])}.")

    else:
        print("Skipping making a vector plot.")

    if SHOW_PLOTS_AFTER_GENERATION:
        plt.show()  # shows both plots

    print("Done!")


if __name__ == "__main__":
    main()
