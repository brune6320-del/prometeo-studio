"""Contrato fijo y backward determinista. CPU siempre; CUDA si está disponible.

No abre datos, fuentes ni exámenes. No entrena sobre un corpus.
"""
import copy
import unittest
import torch
from torch import nn
from modelo import TipoNet


class PoolDeterministaTest(unittest.TestCase):
    def setUp(self):
        self.previous = torch.are_deterministic_algorithms_enabled()
        self.warn = torch.is_deterministic_algorithms_warn_only_enabled()
        self.threads = torch.get_num_threads()
        torch.set_num_threads(2)
        torch.manual_seed(2610)
        torch.use_deterministic_algorithms(True)

    def tearDown(self):
        torch.use_deterministic_algorithms(self.previous, warn_only=self.warn)
        torch.set_num_threads(self.threads)

    def test_pool_valor_y_gradiente_cpu(self):
        for dtype in (torch.float32, torch.float64):
            a = torch.randn(3, 48, 16, 16, dtype=dtype, requires_grad=True)
            b = a.detach().clone().requires_grad_(True)
            fixed = nn.AvgPool2d(4, stride=4)(a)
            legacy = nn.AdaptiveAvgPool2d((4, 4))(b)
            torch.testing.assert_close(fixed, legacy, rtol=0, atol=0)
            grad = torch.randn_like(fixed)
            fixed.backward(grad); legacy.backward(grad)
            torch.testing.assert_close(a.grad, b.grad, rtol=0, atol=0)

    def test_red_y_pesos_anteriores_compatibles(self):
        fixed = TipoNet(12)
        legacy = copy.deepcopy(fixed)
        legacy.conv[-1] = nn.AdaptiveAvgPool2d((4, 4))
        fixed.load_state_dict(legacy.state_dict(), strict=True)
        x = torch.randn(2, 3, 64, 64)
        for a, b in zip(fixed(x), legacy(x)):
            torch.testing.assert_close(a, b, rtol=0, atol=0)

    def test_rechaza_tamano_no_equivalente(self):
        for shape in ((2, 3, 65, 64), (2, 3, 32, 32), (3, 64, 64)):
            with self.assertRaisesRegex(ValueError, '64x64'):
                TipoNet(3)(torch.zeros(shape))

    def backward(self, device):
        net = TipoNet(3).to(device)
        optimizer = torch.optim.SGD(net.parameters(), lr=.01)
        before = net.regresion.weight.detach().clone()
        emb, cls, reg = net(torch.randn(2, 3, 64, 64, device=device))
        loss = cls.square().mean() + reg.square().mean() + emb.square().mean()
        optimizer.zero_grad(); loss.backward(); optimizer.step()
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all()
                            for p in net.parameters()))
        self.assertFalse(torch.equal(before, net.regresion.weight))

    def test_backward_determinista_cpu(self):
        self.backward('cpu')

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA no disponible')
    def test_backward_determinista_cuda(self):
        # Debe fijarse antes de inicializar CUDA, también en CI.
        import os
        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
        self.backward('cuda')


if __name__ == '__main__':
    unittest.main()
