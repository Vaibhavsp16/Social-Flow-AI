import os
import json
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf

from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.layers import *
from tensorflow.keras.models import Model

DATASET_PATH = "ImageNet/dataset"
MAPPING_FILE = "ImageNet/class_mapping.json"

if not os.path.isdir(DATASET_PATH):
    raise FileNotFoundError(f"Dataset directory not found: {DATASET_PATH}")

if not os.path.isfile(MAPPING_FILE):
    raise FileNotFoundError(f"Class mapping file not found: {MAPPING_FILE}")

with open(MAPPING_FILE, "r") as file:
    label_mapping = json.load(file)

classes = sorted([
    cls for cls in os.listdir(DATASET_PATH)
    if os.path.isdir(os.path.join(DATASET_PATH, cls))
])

X, texts = [], []

MAX_IMAGES_PER_CLASS = 100

for cls in classes:
    folder = os.path.join(DATASET_PATH, cls)
    class_name = label_mapping.get(cls, cls.replace("_", " "))

    files = [
        f for f in sorted(os.listdir(folder))
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ][:MAX_IMAGES_PER_CLASS]

    for file in files:
        try:
            img_path = os.path.join(folder, file)

            img = load_img(img_path, target_size=(64, 64))
            img = img_to_array(img)

            X.append(img / 127.5 - 1.0)
            texts.append("a photo of a " + class_name)

        except Exception:
            continue

X = np.array(X, dtype=np.float32)
texts = np.array(texts)

print("Dataset shape:", X.shape)
print("Number of descriptions:", len(texts))
print("Classes:", classes)

if len(X) == 0:
    raise ValueError("No images found. Check the dataset path.")

tokenizer = Tokenizer()
tokenizer.fit_on_texts(texts)

seq = pad_sequences(
    tokenizer.texts_to_sequences(texts),
    maxlen=6,
    padding="post"
)

vocab_size = len(tokenizer.word_index) + 1

ti = Input(shape=(6,))
te = Embedding(vocab_size, 32)(ti)
te = GlobalAveragePooling1D()(te)

text_encoder = Model(ti, te)

text_features = text_encoder.predict(seq, verbose=0)

noise_input = Input(shape=(100,))
text_input = Input(shape=(32,))

g = Concatenate()([noise_input, text_input])
g = Dense(8 * 8 * 128, activation="relu")(g)
g = Reshape((8, 8, 128))(g)

g = Conv2DTranspose(
    64, 4, strides=2,
    padding="same", activation="relu"
)(g)

g = Conv2DTranspose(
    32, 4, strides=2,
    padding="same", activation="relu"
)(g)

g = Conv2DTranspose(
    16, 4, strides=2,
    padding="same", activation="relu"
)(g)

generated_image = Conv2D(
    3, 3, padding="same", activation="tanh"
)(g)

generator = Model(
    [noise_input, text_input],
    generated_image
)

print("Generator output shape:", generator.output_shape)

image_input = Input(shape=(64, 64, 3))
text_input_d = Input(shape=(32,))

d = Conv2D(64, 4, strides=2, padding="same")(image_input)
d = LeakyReLU(negative_slope=0.2)(d)

d = Conv2D(128, 4, strides=2, padding="same")(d)
d = LeakyReLU(negative_slope=0.2)(d)

d = Flatten()(d)
d = Concatenate()([d, text_input_d])

validity = Dense(1, activation="sigmoid")(d)

discriminator = Model(
    [image_input, text_input_d],
    validity
)

discriminator.compile(
    optimizer="adam",
    loss="binary_crossentropy"
)

discriminator.trainable = False

noise_gan = Input(shape=(100,))
text_gan = Input(shape=(32,))

fake = generator([noise_gan, text_gan])
valid = discriminator([fake, text_gan])

gan = Model([noise_gan, text_gan], valid)

gan.compile(
    optimizer="adam",
    loss="binary_crossentropy"
)

epochs = 100
batch_size = min(32, len(X))

if batch_size == 0:
    raise ValueError("The dataset contains no usable images.")

real_labels = np.ones((batch_size, 1), dtype=np.float32)
fake_labels = np.zeros((batch_size, 1), dtype=np.float32)

for epoch in range(epochs):

    idx = np.random.randint(0, len(X), batch_size)

    real_images = X[idx]
    real_text = text_features[idx]

    noise = np.random.normal(
        0, 1, (batch_size, 100)
    ).astype(np.float32)

    fake_images = generator.predict(
        [noise, real_text], verbose=0
    )

    discriminator.trainable = True

    d_loss_real = discriminator.train_on_batch(
        [real_images, real_text], real_labels
    )

    d_loss_fake = discriminator.train_on_batch(
        [fake_images, real_text], fake_labels
    )

    discriminator.trainable = False

    g_loss = gan.train_on_batch(
        [noise, real_text], real_labels
    )

    if epoch % 10 == 0:
        print(
            f"Epoch {epoch}: "
            f"Discriminator Loss = "
            f"{(float(d_loss_real) + float(d_loss_fake)) / 2:.4f}, "
            f"Generator Loss = {float(g_loss):.4f}"
        )

def generate_image(description):
    s = pad_sequences(
        tokenizer.texts_to_sequences([description]),
        maxlen=6,
        padding="post"
    )

    feature = text_encoder.predict(s, verbose=0)

    noise = np.random.normal(
        0, 1, (1, 100)
    ).astype(np.float32)

    img = generator.predict(
        [noise, feature], verbose=0
    )[0]

    img = (img + 1.0) / 2.0

    return np.clip(img, 0, 1)


description = "a photo of a tench"
generated = generate_image(description)

plt.figure(figsize=(5, 5))
plt.imshow(generated)
plt.title("Generated: " + description)
plt.axis("off")
plt.show()

print(f'"{description}"')
print(" ↓")
print("Conditional GAN")
print(" ↓")
print("Generated Image")