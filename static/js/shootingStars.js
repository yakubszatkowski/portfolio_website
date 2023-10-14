function createStar() {
  const shootingStar = document.createElement('span')
  shootingStar.classList.add('shooting-star')

  const randX = Math.random() * window.innerWidth
  const randY = Math.random() * window.innerHeight
  shootingStar.style.left = `${randX}px`
  shootingStar.style.top = `${randY}px`

  const glowingBg = document.querySelector('.glowing-bg')
  glowingBg.appendChild(shootingStar)

  shootingStar.addEventListener('animationiteration', () => {
    glowingBg.removeChild(shootingStar);
    createStar()
  });
}

for (let step = 0; step < 5; step++) {
  const randDelayTime = Math.floor(Math.random() * 5000)
  setTimeout(createStar, randDelayTime)
}
