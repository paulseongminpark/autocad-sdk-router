# Evidence format fallback

evidence.xlsx was not authored because the required @oai/artifact-tool dependency loader (load_workspace_dependencies) is unavailable in this session. The spreadsheet skill forbids guessing dependency paths or substituting openpyxl/xlsxwriter; the packet explicitly permits CSV when XLSX is unavailable.
