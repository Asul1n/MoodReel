# models/

训练产物目录（.npz 已 gitignore，不入库）。

由 `scripts/train_textcnn.py` 生成：

- `vocab.json`   —— 词表（<pad>/<unk> + top-15000 词），训练与线上共用
- `textcnn.npz`  —— 权重（embedding + conv[3,4,5] + fc）

> 生成后即可被 `app/services/textcnn.py` 加载。想让大家免训练直接跑，
> 可单独把该模型文件发给队友放进此目录（不入 git）。
