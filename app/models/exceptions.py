class AppError(Exception):
    """Classe base para todas as exceções do projeto Contar."""
    pass

class NetworkError(AppError):
    """Erro genérico de conectividade."""
    pass

class DeviceOfflineError(NetworkError):
    """Dispositivo não respondeu ao teste de porta (Socket)."""
    pass

class AuthenticationError(NetworkError):
    """Falha de login (Usuário ou Senha incorretos)."""
    pass

class SSHExecutionError(NetworkError):
    """Conexão estabelecida, mas o comando falhou ou o rádio caiu."""
    pass