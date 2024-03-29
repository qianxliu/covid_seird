import codecs
import multiprocessing
import os
import re

import matplotlib.pyplot as plt
import pandas as pd
from pmdarima import arima
from pmdarima.model_selection import train_test_split
from sklearn.metrics import r2_score

province_name = {
    "Anhui": "安徽",
    "Beijing": "北京",
    "Chongqing": "重庆",
    "Fujian": "福建",
    "Gansu": "甘肃",
    "Guangdong": "广东",
    "Guangxi": "广西",
    "Guizhou": "贵州",
    "Hainan": "海南",
    "Hebei": "河北",
    "Heilongjiang": "黑龙江",
    "Henan": "河南",
    "Hong Kong": "香港",
    "Hubei": "湖北",
    "Hunan": "湖南",
    "Inner Mongolia": "内蒙古",
    "Jiangsu": "江苏",
    "Jiangxi": "江西",
    "Jilin": "吉林",
    "Liaoning": "辽宁",
    "Macau": "澳门",
    "Ningxia": "宁夏",
    "Qinghai": "青海",
    "Shaanxi": "陕西",
    "Shandong": "山东",
    "Shanghai": "上海",
    "Shanxi": "山西",
    "Sichuan": "四川",
    "Tianjin": "天津",
    "Tibet": "西藏",
    "Xinjiang": "新疆",
    "Yunnan": "云南",
    "Zhejiang": "浙江",
    "Taiwan": "台湾",
}


def adjust_date(s):
    t = s.split("/")
    return f"20{t[2]}-{int(t[0]):02d}-{int(t[1]):02d}"


def adjust_name(s):
    return re.sub(r"[*,() ']", "_", s)


def draw(model, df, province, isDaily):
    # 模型训练
    if isDaily:
        data = df[province].diff().dropna()
        model.fit(data)
    else:
        data = df[province]
        model.fit(data)

    # 模型验证
    train, test = train_test_split(data, train_size=0.8)
    pred_test = model.predict_in_sample(start=train.shape[0], dynamic=False)
    validating = pd.Series(pred_test, index=test.index)
    r2 = r2_score(test, pred_test)
    print(r2)
    print(province_name[province] + " done!")

    # 开始预测
    pred, pred_ci = model.predict(n_periods=14, return_conf_int=True)
    idx = pd.date_range(data.index.max() + pd.Timedelta("1D"), periods=14, freq="D")
    forecasting = pd.Series(pred, index=idx)

    # 绘图呈现
    plt.figure(figsize=(24, 6))

    plt.plot(data.index, data, label="实际值", color="blue")
    plt.plot(validating.index, validating, label="校验值", color="orange")
    plt.plot(forecasting.index, forecasting, label="预测值", color="red")
    # plt.fill_between(forecasting.index, pred_ci[:, 0], pred_ci[:, 1], color="black", alpha=.25)

    plt.legend()
    plt.ticklabel_format(style="plain", axis="y")
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
    if isDaily:
        plt.title(
            f"每日新增预测 - {province_name[province]}\nARIMA {model.model_.order}x{model.model_.seasonal_order} (R2 = {r2:.6f})"
        )
        plt.savefig(
            os.path.join("figures", f"{adjust_name(province)}-daily.svg"),
            bbox_inches="tight",
        )
        plt.close()
    else:
        plt.title(
            f"累计确诊预测 - {province_name[province]}\nARIMA {model.model_.order}x{model.model_.seasonal_order} (R2 = {r2:.6f})"
        )
        plt.savefig(
            os.path.join("figures", f"{adjust_name(province)}.svg"), bbox_inches="tight"
        )
        plt.close()


if __name__ == "__main__":
    # 准备数据
    df = pd.read_csv(
        "time_series_covid19_confirmed_global.csv",
        index_col="Province/State",
    ).drop(columns=["Lat", "Long"])
    df = (
        df[(df["Country/Region"] == "China") | (df["Country/Region"] == "Taiwan*")]
            .transpose()
            .drop("Country/Region")
            .rename(columns=str)
            .rename(columns={"nan": "Taiwan"})
            .drop(columns=["Unknown"])
            .sort_index(axis=1)
    )
    df.index = pd.DatetimeIndex(df.index.map(adjust_date))

    provinces = df.columns.to_list()

    model = arima.AutoARIMA(
        start_p=0,
        max_p=4,
        d=None,
        start_q=0,
        max_q=1,
        start_P=0,
        max_P=1,
        D=None,
        start_Q=0,
        max_Q=1,
        m=7,
        seasonal=True,
        test="kpss",
        trace=True,
        error_action="ignore",
        suppress_warnings=True,
        stepwise=True,
    )


    # plt无法线程安全，使用异步进程
    def process_result(return_value):
        print(return_value)


    pool = multiprocessing.Pool()
    for i in range(len(provinces)):
        pool.apply_async(draw, args=(model, df, provinces[i], False), callback=process_result)
        pool.apply_async(draw, args=(model, df, provinces[i], True), callback=process_result)
    pool.close()
    pool.join()

    # 编制索引
    with codecs.open("ARIMA_Province.md", "w", "utf-8") as f:
        f.write("# COVID-19 Forecasting\n\n")
        f.write(
            "[![Province application](https://github.com/Neteraxe/covid_seird/actions/workflows/province-app.yml/badge.svg)](https://github.com/Neteraxe/covid_seird/actions/workflows/province-app.yml)\n"
        )
        f.write(
            "[![Data Source](https://img.shields.io/badge/Data%20Source-https://github.com/CSSEGISandData/COVID--19-brightgreen)](https://github.com/CSSEGISandData/COVID-19)\n"
        )
        for province in provinces:
            f.write(f"## {province_name.get(province, province)}\n\n")
            f.write(f"![img](figures/{adjust_name(province)}.svg)\n\n")
            f.write(f"![img](figures/{adjust_name(province)}-daily.svg)\n\n")
