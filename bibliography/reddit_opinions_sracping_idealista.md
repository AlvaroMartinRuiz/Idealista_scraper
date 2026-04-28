## TIPS ON HOW TO SCRAP IDEALISTA FROM REDDIT

### FIRST COMMENT
Hola,

Idealista usa DataDome, que es una de las soluciones anti-bot más agresivas que hay. Un par de cosas importantes:

Proxies residenciales son prácticamente imprescindibles — las IPs de centros de datos se marcan al instante

La huella digital del navegador es el verdadero desafío. Comprueban la huella digital TLS, el canvas, WebGL y las propiedades del navegador. Herramientas como undetected-chromedriver o Playwright con plugins stealth ayudan, pero tienes que mantenerlas actualizadas

Limitación de la frecuencia de peticiones — ralentiza tus peticiones significativamente. DataDome rastrea los patrones de peticiones, así que retrasos aleatorios entre 5 y 15 segundos por página ayudan

Gestión de cookies/sesiones — soluciona el desafío inicial una vez, luego reutiliza las cookies de sesión para peticiones posteriores

La gente que tiene éxito de forma consistente usa una combinación de rotación residencial + emulación de navegador adecuada en lugar de simplemente lanzar proxies.

Espero que esto ayude.

### SECOND COMMENT:
¿Cómo evito que me detecten patrones de solicitudes a gran escala? ¿Un hilo sin retrasos tendría el mismo efecto que dos hilos con retrasos, no? Y en ese momento me pillarían.

Respuesta:
Retrasos aleatorios por sesión, asegúrate de mover el ratón, asegúrate de teclear y hacer scroll como un humano, velocidad de escritura aleatoria, velocidad de scroll aleatoria. Cada sesión tiene que parecer única.

Si puedes aleatorizar el patrón de navegación, mejor que mejor.

Normalmente tengo 3-4 rutas de navegación, y luego cada sesión tiene una ruta aleatoria con todos los demás aspectos también aleatorizados...