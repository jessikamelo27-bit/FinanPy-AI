"""
Gerador do executável nativo Windows (FinanPy AI PRO.exe) com ícone personalizado.
Compila um executável GUI (/target:winexe) que:
1. Verifica se o servidor Flask local (127.0.0.1:5000) já está ativo;
2. Se não estiver, inicia o servidor em segundo plano (sem janela de terminal preta);
3. Abre a interface do FinanPy AI PRO em modo aplicativo nativo (--app=http://127.0.0.1:5000).
"""

import os
import struct
import subprocess
import zlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT_DIR / "static" / "img" / "finanpy.ico"
CS_PATH = ROOT_DIR / "desktop" / "FinanPyLauncher.cs"
EXE_PROJECT_PATH = ROOT_DIR / "FinanPy AI PRO.exe"
EXE_DESKTOP_PATH = Path(r"C:\Users\SEMADI\Desktop\FinanPy AI PRO.exe")


def _criar_png_icone(tamanho: int = 64) -> bytes:
    """Gera um ícone PNG 64x64 em estilo Dark Fintech (gradiente azul/roxo com símbolo central)."""
    width = height = tamanho
    raw_rows = []
    centro = (tamanho - 1) / 2.0
    raio_max = tamanho * 0.46

    for y in range(height):
        row = bytearray([0])  # filtro PNG None
        for x in range(width):
            # Canto arredondado (squircle)
            dx = abs(x - centro)
            dy = abs(y - centro)
            dist_canto = max(dx, dy)
            dist_euclid = (dx * dx + dy * dy) ** 0.5

            if dist_canto > raio_max or dist_euclid > raio_max * 1.18:
                row.extend((0, 0, 0, 0))
                continue

            # Gradiente diagonal (#3b82f6 -> #6366f1 -> #1e1b4b)
            t = (x + y) / (2.0 * tamanho)
            r = int(59 * (1 - t) + 99 * t)
            g = int(130 * (1 - t) + 70 * t)
            b = int(246 * (1 - t) + 229 * t)

            # Borda iluminada sutil
            if dist_canto > raio_max - 2.2:
                r = min(255, r + 45)
                g = min(255, g + 45)
                b = min(255, b + 45)

            # Desenha um símbolo "F$" estilizado / barras de gráfico ascendentes em branco no centro
            nx = (x - tamanho * 0.22) / (tamanho * 0.56)
            ny = (y - tamanho * 0.22) / (tamanho * 0.56)

            is_bar1 = (0.12 <= nx <= 0.28) and (0.52 <= ny <= 0.85)
            is_bar2 = (0.42 <= nx <= 0.58) and (0.32 <= ny <= 0.85)
            is_bar3 = (0.72 <= nx <= 0.88) and (0.12 <= ny <= 0.85)
            is_base = (0.08 <= nx <= 0.92) and (0.83 <= ny <= 0.91)

            if is_bar1 or is_bar2 or is_bar3 or is_base:
                row.extend((248, 250, 252, 255))
            else:
                row.extend((r, g, b, 255))

        raw_rows.append(bytes(row))

    raw_data = b"".join(raw_rows)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw_data, 9)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def gerar_ico(caminho_ico: Path) -> None:
    """Empacota o PNG 64x64 em um arquivo .ICO válido do Windows."""
    caminho_ico.parent.mkdir(parents=True, exist_ok=True)
    png_bytes = _criar_png_icone(64)
    header = struct.pack("<HHH", 0, 1, 1)
    direntry = struct.pack(
        "<BBBBHHII",
        64,  # width
        64,  # height
        0,   # palette
        0,   # reserved
        1,   # color planes
        32,  # bits per pixel
        len(png_bytes),
        6 + 16,  # offset
    )
    caminho_ico.write_bytes(header + direntry + png_bytes)


def gerar_codigo_csharp(caminho_cs: Path, root_dir: Path) -> None:
    """Gera o código C# do inicializador nativo do FinanPy AI PRO."""
    root_escaped = str(root_dir).replace("\\", "\\\\")
    codigo = f"""using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Threading;
using System.Windows.Forms;

namespace FinanPyLauncher
{{
    static class Program
    {{
        private const string AppUrl = "http://127.0.0.1:5000";
        private const string HealthUrl = "http://127.0.0.1:5000/api/categorias";
        private const string ProjectDir = "{root_escaped}";

        [STAThread]
        static void Main()
        {{
            try
            {{
                if (!ServidorEstaAtivo())
                {{
                    IniciarServidorEmSegundoPlano();
                    AguardarServidorSubir(10000);
                }}

                AbrirJanelaAplicativo();
            }}
            catch (Exception ex)
            {{
                MessageBox.Show(
                    "Não foi possível iniciar o FinanPy AI PRO:\\n\\n" + ex.Message,
                    "FinanPy AI PRO",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }}
        }}

        private static bool ServidorEstaAtivo()
        {{
            try
            {{
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create(HealthUrl);
                req.Timeout = 700;
                req.Method = "GET";
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                {{
                    return resp.StatusCode == HttpStatusCode.OK;
                }}
            }}
            catch
            {{
                return false;
            }}
        }}

        private static void IniciarServidorEmSegundoPlano()
        {{
            string pythonExe = Path.Combine(ProjectDir, ".venv", "Scripts", "pythonw.exe");
            if (!File.Exists(pythonExe))
            {{
                pythonExe = Path.Combine(ProjectDir, ".venv", "Scripts", "python.exe");
            }}
            string appPy = Path.Combine(ProjectDir, "app.py");

            if (!File.Exists(appPy))
            {{
                throw new FileNotFoundException("Arquivo principal não encontrado em: " + appPy);
            }}

            ProcessStartInfo psi = new ProcessStartInfo
            {{
                FileName = pythonExe,
                Arguments = "\\"" + appPy + "\\"",
                WorkingDirectory = ProjectDir,
                CreateNoWindow = true,
                UseShellExecute = false,
                WindowStyle = ProcessWindowStyle.Hidden
            }};

            Process.Start(psi);
        }}

        private static void AguardarServidorSubir(int timeoutMs)
        {{
            int decorrido = 0;
            while (decorrido < timeoutMs)
            {{
                if (ServidorEstaAtivo())
                {{
                    return;
                }}
                Thread.Sleep(200);
                decorrido += 200;
            }}
        }}

        private static void AbrirJanelaAplicativo()
        {{
            string[] navegadores = new string[]
            {{
                @"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                @"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                @"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                @"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"
            }};

            foreach (string nav in navegadores)
            {{
                if (File.Exists(nav))
                {{
                    ProcessStartInfo psi = new ProcessStartInfo
                    {{
                        FileName = nav,
                        Arguments = "--app=" + AppUrl + " --window-size=1440,920",
                        UseShellExecute = true
                    }};
                    Process.Start(psi);
                    return;
                }}
            }}

            Process.Start(new ProcessStartInfo
            {{
                FileName = AppUrl,
                UseShellExecute = true
            }});
        }}
    }}
}}
"""
    caminho_cs.parent.mkdir(parents=True, exist_ok=True)
    caminho_cs.write_text(codigo, encoding="utf-8")


def compilar_executavel() -> None:
    gerar_ico(ICON_PATH)
    gerar_codigo_csharp(CS_PATH, ROOT_DIR)

    csc = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    for destino in (EXE_PROJECT_PATH, EXE_DESKTOP_PATH):
        cmd = [
            csc,
            "/nologo",
            "/target:winexe",
            "/optimize+",
            f"/out:{destino}",
            f"/win32icon:{ICON_PATH}",
            "/r:System.dll",
            "/r:System.Windows.Forms.dll",
            str(CS_PATH),
        ]
        subprocess.run(cmd, check=True)
        print(f"Executável gerado com sucesso: {destino}")


if __name__ == "__main__":
    compilar_executavel()
