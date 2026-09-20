"""Localized prose for the offline referee; verdicts and code identifiers stay intact."""

_TEXT = {
    "messi": {
        "categories": {"security": "seguridad", "reliability": "fiabilidad", "maintainability": "mantenimiento"},
        "added": "Detecté un posible problema de {category}: aparece '{pattern}' en los cambios que vas a enviar.",
        "removed": "Se eliminó una línea con '{pattern}'; puede que se haya perdido una protección.",
        "restore": "Restaurá la protección '{pattern}' o indicá dónde se sigue aplicando.",
        "clean": "No detecté patrones sospechosos en los cambios que vas a enviar.",
        "overturned": "Las nuevas pruebas respaldan lo que explicaste: las llamadas comparables o sus llamadores confirman que la protección está presente.",
        "upheld": "Las nuevas pruebas no respaldan lo que explicaste. No encontré contexto del repositorio ni de los llamadores que confirme esa protección.",
        "roast": "Revisemos esta jugada antes de seguir.",
        "clean_roast": "Buena jugada, no hace falta silbato.",
        "overturned_roast": "Tenías razón, me equivoqué. ¡Siga, siga!",
        "upheld_roast": "Buen intento, pero el VAR necesita pruebas.",
        "fixes": {
            "eval(": "Reemplazá eval() por ast.literal_eval() para datos, o analizá la entrada explícitamente. Nunca ejecutes cadenas de texto.",
            "exec(": "Eliminá exec(). Llamá directamente a la función necesaria o usá un diccionario de manejadores permitidos.",
            "DROP TABLE": "Mové el cambio de esquema a una migración revisada y no construyas DDL con cadenas en tiempo de ejecución.",
            "password": "Cargá el secreto desde una variable de entorno o un gestor de secretos y comparalo con hmac.compare_digest().",
            "TODO": "Terminá el trabajo o creá una tarea y enlazala en el comentario para no perder el seguimiento.",
            "except:": "Capturá las excepciones específicas que esperás y registrá o relanzá las demás.",
            "except Exception:": "Capturá las excepciones específicas que esperás y registrá o relanzá las demás.",
            "console.log": "Eliminá el registro de depuración o usá el sistema de registro del proyecto en nivel debug.",
            "timeout": "Configurá un tiempo límite explícito para la llamada y manejá el error cuando se agote.",
            "AbortSignal": "Seguí pasando AbortSignal para que la solicitud pueda cancelarse.",
        },
    },
    "ronaldo": {
        "categories": {"security": "segurança", "reliability": "fiabilidade", "maintainability": "manutenção"},
        "added": "Detetei um possível problema de {category}: o padrão '{pattern}' aparece nas alterações a enviar.",
        "removed": "Foi removida uma linha com '{pattern}', o que pode eliminar uma proteção.",
        "restore": "Repõe a proteção '{pattern}' ou indica onde continua a ser aplicada.",
        "clean": "Não detetei padrões suspeitos nas alterações a enviar.",
        "overturned": "As novas provas confirmam a tua explicação: chamadas comparáveis ou os seus chamadores demonstram que a proteção está presente.",
        "upheld": "As novas provas não confirmam a tua explicação. Não encontrei contexto do repositório nem dos chamadores que demonstre essa proteção.",
        "roast": "Vamos corrigir esta jogada e voltar mais fortes.",
        "clean_roast": "Jogada limpa. Segue o jogo!",
        "overturned_roast": "Tinhas razão, o árbitro enganou-se. Segue o jogo!",
        "upheld_roast": "Boa tentativa, mas o VAR exige provas.",
        "fixes": {
            "eval(": "Substitui eval() por ast.literal_eval() para dados, ou analisa a entrada explicitamente. Nunca executes cadeias de texto.",
            "exec(": "Remove exec(). Chama diretamente a função necessária ou usa um dicionário de funções permitidas.",
            "DROP TABLE": "Move a alteração de esquema para uma migração revista e nunca construas DDL a partir de texto em tempo de execução.",
            "password": "Obtém o segredo de uma variável de ambiente ou de um gestor de segredos e compara-o com hmac.compare_digest().",
            "TODO": "Conclui o trabalho ou cria uma tarefa e referencia-a no comentário para garantir o acompanhamento.",
            "except:": "Captura as exceções específicas que esperas e regista ou volta a lançar as restantes.",
            "except Exception:": "Captura as exceções específicas que esperas e regista ou volta a lançar as restantes.",
            "console.log": "Remove o registo de depuração ou usa o sistema de registo do projeto no nível debug.",
            "timeout": "Define um tempo limite explícito para a chamada e trata o erro quando esse limite for atingido.",
            "AbortSignal": "Continua a passar AbortSignal para permitir o cancelamento do pedido.",
        },
    },
    "son": {
        "categories": {"security": "보안", "reliability": "안정성", "maintainability": "유지보수"},
        "added": "전송할 변경 사항에서 '{pattern}' 패턴이 발견되어 {category} 문제가 있을 수 있습니다.",
        "removed": "'{pattern}'이 포함된 줄이 삭제되어 보호 장치가 사라졌을 수 있습니다.",
        "restore": "'{pattern}' 보호 장치를 복원하거나 어디에서 계속 적용되는지 알려 주세요.",
        "clean": "전송할 변경 사항에서 의심스러운 패턴을 발견하지 못했습니다.",
        "overturned": "새로운 근거가 개발자님의 설명을 뒷받침합니다. 유사한 호출 지점이나 호출자에서 해당 보호 장치가 유지되고 있음을 확인했습니다.",
        "upheld": "새로운 근거가 개발자님의 설명을 뒷받침하지 못합니다. 해당 보호 장치를 확인할 수 있는 호출자나 저장소 맥락을 찾지 못했습니다.",
        "roast": "이 부분을 함께 다듬고 다시 뛰어 봐요!",
        "clean_roast": "깔끔한 플레이입니다. 계속 진행하세요!",
        "overturned_roast": "말씀이 맞았습니다. 심판의 실수였네요. 계속 진행하세요!",
        "upheld_roast": "좋은 시도지만 VAR에는 근거가 필요합니다.",
        "fixes": {
            "eval(": "데이터에는 eval() 대신 ast.literal_eval()을 사용하거나 입력을 명시적으로 파싱해 주세요. 문자열을 실행하지 마세요.",
            "exec(": "exec()를 제거하고 필요한 함수를 직접 호출하거나 허용된 처리 함수 사전을 사용해 주세요.",
            "DROP TABLE": "스키마 변경을 검토된 마이그레이션으로 옮기고 실행 중 문자열로 DDL을 만들지 마세요.",
            "password": "환경 변수나 비밀 관리 도구에서 비밀 값을 불러오고 hmac.compare_digest()로 비교해 주세요.",
            "TODO": "작업을 완료하거나 작업 항목을 만들고 주석에 연결해 후속 작업을 놓치지 않도록 해 주세요.",
            "except:": "예상하는 구체적인 예외를 처리하고 나머지는 기록하거나 다시 발생시켜 주세요.",
            "except Exception:": "예상하는 구체적인 예외를 처리하고 나머지는 기록하거나 다시 발생시켜 주세요.",
            "console.log": "디버그 출력을 제거하거나 프로젝트의 로깅 도구를 debug 수준으로 사용해 주세요.",
            "timeout": "호출에 명시적인 제한 시간을 설정하고 시간 초과 오류를 처리해 주세요.",
            "AbortSignal": "요청을 취소할 수 있도록 AbortSignal을 계속 전달해 주세요.",
        },
    },
}


def localized_fields(level: str, event: str, category: str, pattern: str = "") -> dict[str, str]:
    text = _TEXT.get(level)
    if text is None:
        return {}
    result = {
        "explanation": text[event].format(category=text["categories"].get(category, category), pattern=pattern),
        "roast": text.get(f"{event}_roast", text["roast"]),
    }
    if event == "added":
        result["suggested_fix"] = text["fixes"][pattern]
    elif event == "removed":
        result["suggested_fix"] = text["restore"].format(pattern=pattern)
    return result
