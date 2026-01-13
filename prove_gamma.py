import numpy as np
from scipy.optimize import curve_fit

# Dati





exp = np.array([250,300,350,400,450,500,550,600,650,700,750,800])
valori = np.array([60,94,118,144,166,183,199,212,219,225,231,236])  # Valori pixel letti

exp = np.array([50,60,70,80,90,100,110,125])
valori = np.array([101,136,166,190,210,218,225,237])

exp = np.array([150,200,250,300,350,400,450,500,550])
valori = np.array([44,96,135,166,194,214,223,233,237])

exp = np.array([50,100,200,300,400,  500,600])#,500,550])
valori = np.array([16,24,103,151,208,  237,240])#,233,237])

def risposta(exp,g, l):
    #c = 12**g/255**(g-1)
    c=0
    a=255-c
    r=255*((a*(1-np.exp(-l*exp))+c)/255)**(1/g)
    return r



# Fit con limiti ragionevoli
popt, _ = curve_fit(
    risposta,
    exp,
    valori,
  #  p0=[2,30],
    bounds=([ 0, 0], [ np.inf, 1e-1])  # gamma 0.5–5, l tra 0.0001 e 1
)

g, l = popt
print(f" gamma = {g:.6e}, lambda = {l:.6f}")


import matplotlib.pyplot as plt

# Genera punti per il fit
exp_fit = np.linspace(min(exp), max(exp), 200)
valori_fit = risposta(exp_fit, *popt)

# Plot
plt.plot(exp, valori, 'o', label='Dati misurati')
plt.plot(exp_fit, valori_fit, '-', label='Modello fit')
plt.xlabel('Tempo di esposizione')
plt.ylabel('Valore pixel')
plt.title('Fit risposta sensore con saturazione e gamma')
plt.grid(True)
plt.legend()
plt.show()
