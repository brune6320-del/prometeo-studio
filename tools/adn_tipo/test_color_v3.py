"""Contratos numéricos con tensores artificiales; sin corpus ni entrenamiento."""
import math
import unittest

import numpy as np
from PIL import Image
import torch
from skimage.color import deltaE_ciede2000

from comun import ROOT, sha256
from entrenar_v3 import componentes, validar
from modelo import TipoNet, prediccion_red
from protocolo_v3 import PRERREGISTRO_SHA


class ColorV3Test(unittest.TestCase):
    def test_pesos_y_gradientes_de_la_perdida_prerregistrada(self):
        pred = torch.tensor([[1., .6, -.25, .5]], dtype=torch.float64, requires_grad=True)
        truth = torch.tensor([[.5, .4, -.125, .25]], dtype=torch.float64)
        logits = torch.zeros((1, 2), dtype=torch.float64, requires_grad=True)
        score, ce, size, color = componentes(logits, pred, torch.tensor([0]), truth)
        self.assertAlmostEqual(ce.item(), math.log(2))
        self.assertAlmostEqual(size.item(), .5**2)
        self.assertAlmostEqual(color.item(), (.2**2 + .125**2 + .25**2) / 3)
        self.assertAlmostEqual(score.item(), math.log(2) + .5**2 + 4 * color.item())
        # Solo backward de tensores: no optimizador, pesos ni pasos de entrenamiento.
        score.backward()
        expected = torch.tensor([[1., 8*.2/3, -8*.125/3, 8*.25/3]], dtype=torch.float64)
        torch.testing.assert_close(pred.grad, expected, rtol=1e-12, atol=1e-12)

    def test_cabeza_lineal_preserva_signo_lab_y_unidades_de_inferencia(self):
        net = TipoNet(2).double().eval()
        with torch.no_grad():
            net.regresion.weight.zero_()
            net.regresion.bias.copy_(torch.tensor([.75, .5, -.25, .125], dtype=torch.float64))
        # La API de imagen produce float32; mantener el modelo con ese contrato.
        net = net.float()
        _, size, lab = prediccion_red(net, Image.new('RGB', (64, 64), 'white'))
        self.assertEqual(size, 18.)
        np.testing.assert_array_equal(lab, [50., -32., 16.])

    def test_validacion_mide_color_en_lab_fisico_no_en_normalizado(self):
        truth = np.array([[18., 50., -32., 16.], [24., 75., 16., -32.]])
        predicted = truth + np.array([2., 1., -2., 3.])
        scale = np.array([24., 100., 128., 128.])

        class RespuestaFija(torch.nn.Module):
            def forward(self, x):
                return (torch.zeros((2, 32)), torch.eye(2),
                        torch.tensor(predicted / scale, dtype=torch.float64))

        metrics, rows = validar(RespuestaFija(), torch.zeros((2, 3, 64, 64)),
                               torch.tensor([0, 1]), torch.tensor(truth / scale),
                               [0, 1], 'cpu', 2, lambda: None)
        self.assertAlmostEqual(metrics['mae_tamano_pt'], 2.)
        np.testing.assert_allclose(metrics['mae_lab'], [1., 2., 3.], rtol=0, atol=1e-12)
        expected = deltaE_ciede2000(truth[:, 1:], predicted[:, 1:])
        self.assertAlmostEqual(metrics['deltaE2000'], float(expected.mean()))
        self.assertAlmostEqual(metrics['deltaE2000_p95'], float(np.percentile(expected, 95)))
        np.testing.assert_allclose(rows['prediccion_tamano_lab'], predicted)
        np.testing.assert_allclose(rows['etiqueta_tamano_lab'], truth)

    def test_prerregistros_sellados(self):
        self.assertEqual(sha256(ROOT / 'PRERREGISTRO.md'),
                         '16b5a933c466c04eaa9a28e06dcb62ceb4be2c66b73e1391b1a16d546637d776')
        self.assertEqual(sha256(ROOT / 'PRERREGISTRO-v3.md'), PRERREGISTRO_SHA)


if __name__ == '__main__':
    unittest.main()
