using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

namespace FAALauncher
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            string exePath = Assembly.GetExecutingAssembly().Location;
            string appDir = Path.GetDirectoryName(exePath) ?? AppDomain.CurrentDomain.BaseDirectory;
            string launcherPath = Path.Combine(appDir, "plugins", "launcher_scripts", "AppInstallRun.bat");

            if (!File.Exists(launcherPath))
            {
                MessageBox.Show(
                    "The FAA startup script was not found:" + Environment.NewLine + launcherPath,
                    "FAA startup failed",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }

            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = launcherPath,
                    Arguments = QuoteArguments(args),
                    WorkingDirectory = appDir,
                    UseShellExecute = true,
                    WindowStyle = ProcessWindowStyle.Normal
                };
                Process.Start(startInfo);
                return 0;
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Failed to start the FAA startup script:" + Environment.NewLine + ex.Message,
                    "FAA startup failed",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }
        }

        private static string QuoteArguments(string[] args)
        {
            if (args == null || args.Length == 0)
            {
                return string.Empty;
            }

            string[] quoted = new string[args.Length];
            for (int i = 0; i < args.Length; i++)
            {
                quoted[i] = QuoteArgument(args[i]);
            }
            return string.Join(" ", quoted);
        }

        private static string QuoteArgument(string arg)
        {
            if (string.IsNullOrEmpty(arg))
            {
                return "\"\"";
            }

            bool needsQuotes = arg.IndexOfAny(new[] { ' ', '\t', '\n', '\r', '"' }) >= 0;
            if (!needsQuotes)
            {
                return arg;
            }

            StringBuilder builder = new StringBuilder();
            builder.Append('"');
            int backslashes = 0;
            foreach (char ch in arg)
            {
                if (ch == '\\')
                {
                    backslashes++;
                    continue;
                }

                if (ch == '"')
                {
                    builder.Append('\\', backslashes * 2 + 1);
                    builder.Append('"');
                    backslashes = 0;
                    continue;
                }

                if (backslashes > 0)
                {
                    builder.Append('\\', backslashes);
                    backslashes = 0;
                }
                builder.Append(ch);
            }

            if (backslashes > 0)
            {
                builder.Append('\\', backslashes * 2);
            }
            builder.Append('"');
            return builder.ToString();
        }
    }
}
