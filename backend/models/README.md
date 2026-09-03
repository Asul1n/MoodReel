# models/

推理用模型目录（`*.pt` 已 gitignore，**不入库**，团队内互相拷贝/由成员B提供）。

- `model.pt` —— 成员B训练的 TextCNN checkpoint，内容：
  `{"model": state_dict, "config": {...}, "vocab": {...}}`
  - 数据：IMDB（aclImdb）2.5 万训练；**准确率 86.05%**（≥85% ✅）；GloVe 预训练词向量微调
  - 结构：TextCNN（embed 100 + conv[3,4,5]×100 + 池化 + fc）
  - 来源交付包：`textcnn_sentiment_delivery/textcnn_sentiment/`

放置方式：
```bash
# 把队友的 model.pt 放到这里
cp <textcnn_sentiment_delivery>/textcnn_sentiment/model.pt backend/models/model.pt
# 启动后端后 /health 的 model_ready 会变 true
```

> 训练/评测脚本与完整说明在成员B的交付包中；本仓库 `app/model_runtime/train.py`
> 为与其一致的模型/分词代码（保证推理对得上训练）。
