﻿# overray-status

Windows PC の状態を表示するオーバーレイアプリです。GPU0, GPU1, CPU, メモリ, ドライブ、ネットワーク速度をリアルタイムで表示します。

![screenshot](images/screenshot.png)

## 概要

画面右上に表示される半透明のエリアでリソースをリアルタイムで確認できます。

## 機能

- GPU の表示（VRAM, TEMP, FAN, PWR, LOAD）
- CPU の表示（LOAD）
- メモリ（使用サイズ / 最大サイズ）
- ドライブ（SMART による容量と温度）
- ネットワーク（DOWN, UP の速度）

## インストール

1. 依存関係をインストールします。

```sh
pip install -r requirements.txt
```

2. 起動スクリプトを実行します。

```sh
powershell -ExecutionPolicy Bypass -File start_overlay.ps1
```

3. 停止スクリプトを実行します。

```sh
powershell -ExecutionPolicy Bypass -File stop_overlay.ps1
```

## 起動スクリプト一覧

| スクリプト | 説明 |
| --- | --- |
| `start_overlay.ps1` | バックグラウンドで起動します。 |
| `start_overlay_admin.ps1` | Administrator 権限で起動します。CPU 電力を正確に取得できます。初回は UAC ダイアログが表示されます。「はい」を選択してください。 |
| `stop_overlay.ps1` | 起動したオーバーレイを停止します。 |
| `install_startup.ps1` | ログオン時に自動起動するためのショートカットを配置します。 |
| `uninstall_startup.ps1` | ログオン自動起動ショートカットを削除します。 |

## 使用技術

- Python 3.12+
- PySide6
- psutil
- pynvml
- pySMART（ドライブの SMART データ取得）

## ライセンス

[Apache 2.0](LICENSE)
