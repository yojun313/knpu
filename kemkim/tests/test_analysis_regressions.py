"""Regression coverage for signal boundaries and analysis worker cleanup."""

import multiprocessing
import os
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch

import pandas as pd

from kemkim.app.libs import kemkim as engine


class SignalBoundaryTests(unittest.TestCase):
    def test_each_word_has_one_signal_in_both_maps(self):
        coordinates = {
            "axis": (10, 20),
            "strong": (11, 21),
            "weak": (9, 21),
            "latent": (9, 19),
            "known": (11, 19),
            "both_equal": (10, 20),
            "x_equal_high": (10, 21),
            "x_equal_low": (10, 19),
            "y_equal_high": (11, 20),
            "y_equal_low": (9, 20),
        }
        expected = {
            "strong_signal": sorted(
                ["strong", "both_equal", "x_equal_high", "y_equal_high"]
            ),
            "weak_signal": ["weak", "y_equal_low"],
            "latent_signal": ["latent"],
            "well_known_signal": ["known", "x_equal_low"],
        }
        analyzer = engine.KemKim(modify_kemkim=True, exception_word_list=[])
        for method in (analyzer.DoV_draw_graph, analyzer.DoD_draw_graph):
            with (
                self.subTest(map=method.__name__),
                tempfile.TemporaryDirectory() as folder,
            ):
                with patch.object(engine.plt, "savefig"):
                    signals, saved_coordinates = method(
                        graph_folder=folder,
                        redraw_option=True,
                        coordinates=coordinates,
                        graph_size=(2, 2, 6, 3, 6, 6),
                    )
                self.assertEqual(signals, expected)
                words = [word for group in signals.values() for word in group]
                self.assertEqual(len(words), len(set(words)))
                self.assertEqual(set(words), set(coordinates) - {"axis"})
                self.assertEqual(saved_coordinates["axis"], (10, 20))


class WorkerCleanupTests(unittest.TestCase):
    @unittest.skipUnless(
        "fork" in multiprocessing.get_all_start_methods(), "requires fork"
    )
    def test_finishing_analysis_preserves_other_pool(self):
        context = multiprocessing.get_context("fork")
        figure = engine.plt.figure

        def small_figure(*args, **kwargs):
            kwargs["figsize"] = (2, 2)
            return figure(*args, **kwargs)

        def analysis_pool(**kwargs):
            return ProcessPoolExecutor(max_workers=2, mp_context=context)

        with ProcessPoolExecutor(max_workers=1, mp_context=context) as other_pool:
            other_pid = other_pool.submit(os.getpid).result(timeout=10)
            with tempfile.TemporaryDirectory() as folder:
                analyzer = engine.KemKim(
                    token_data=pd.DataFrame(
                        {
                            "Date": ["2020-01-01", "2021-01-01", "2022-01-01"],
                            "Text": ["alpha, beta, gamma, delta"] * 3,
                        }
                    ),
                    csv_name="token_test.csv",
                    save_path=folder,
                    startdate="20200101",
                    enddate="20221231",
                    period="1y",
                    topword=10,
                    weight=0.1,
                    graph_wordcnt=10,
                    split_option="평균(Mean)",
                    filter_option=True,
                    trace_standard="startyear",
                    ani_option=False,
                    exception_word_list=[],
                )
                with (
                    patch.object(engine, "ProcessPoolExecutor", analysis_pool),
                    patch.object(engine.plt, "figure", small_figure),
                    patch.object(engine.plt, "savefig"),
                ):
                    result = analyzer.make_kemkim()
                self.assertEqual(result, analyzer.kemkim_folder_path)
                self.assertTrue(
                    os.path.isfile(
                        os.path.join(result, "Result", "Signal", "Final_signal.csv")
                    )
                )
                self.assertEqual(
                    other_pool.submit(os.getpid).result(timeout=10), other_pid
                )
                self.assertEqual(
                    {child.pid for child in multiprocessing.active_children()},
                    {other_pid},
                )


if __name__ == "__main__":
    unittest.main()
