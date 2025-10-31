// WSX Image Extractor - Kör detta i F12-konsolen på https://worldsupercrosschampionship.com/riders/
// Detta script extraherar alla förare-bilder och laddar ner dem med korrekt namnformat

(function() {
  console.log('🚀 WSX Image Extractor startar...');
  
  // Funktion för att normalisera namn till filnamn
  function slugify(name) {
    return (name || '').toLowerCase()
      .trim()
      .replace(/\./g, '')
      .replace(/\s+/g, '_')
      .replace(/[^a-z0-9_]/g, '');
  }
  
  // Funktion för att extrahera nummer från text
  function extractNumber(text) {
    const match = (text || '').match(/(?:^|[#\s])(\d{1,3})(?:\s|$)/);
    return match ? parseInt(match[1]) : null;
  }
  
  // Funktion för att ladda ner en bild
  function downloadImage(url, filename) {
    fetch(url)
      .then(res => res.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(err => console.error('Fel vid nedladdning:', filename, err));
  }
  
  // Funktion för att konvertera base64/data URL till blob och ladda ner
  function downloadDataURL(dataUrl, filename) {
    fetch(dataUrl)
      .then(res => res.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(err => console.error('Fel vid nedladdning:', filename, err));
  }
  
  // Hitta alla rider-kort/sektioner på sidan
  const riders = [];
  
  // Strategi 1: Leta efter rider-kort baserat på strukturen från sidan
  // Varje rider verkar ha: nummer, namn, flagga, team, bild
  const cards = document.querySelectorAll('[class*="rider"], [class*="Rider"], article, .card, [data-rider]');
  
  cards.forEach((card, idx) => {
    // Försök hitta text som ser ut som nummer (stor text, # prefix)
    const numberText = card.textContent.match(/(?:^|[#\s])(\d{1,3})(?:\s|$)/);
    const number = numberText ? parseInt(numberText[1]) : null;
    
    // Försök hitta namn (oftast i h2, h3, .name, eller första stor text)
    let name = null;
    const nameEl = card.querySelector('h2, h3, h4, [class*="name"], [class*="Name"], .title');
    if (nameEl) {
      name = nameEl.textContent.trim();
      // Ta bort location (efter komma)
      if (name.includes(',')) name = name.split(',')[0].trim();
    } else {
      // Fallback: försök extrahera från hela texten
      const text = card.textContent.trim();
      const lines = text.split('\n').filter(l => l.trim());
      if (lines.length > 0) {
        // Första raden som är inte nummer och inte för kort
        for (const line of lines) {
          const clean = line.trim();
          if (clean.length > 3 && clean.length < 30 && !clean.match(/^\d+$/)) {
            name = clean;
            break;
          }
        }
      }
    }
    
    // Hitta bild
    let imgUrl = null;
    const img = card.querySelector('img');
    if (img) {
      // Prioritera srcset eller src
      imgUrl = img.srcset ? img.srcset.split(',')[0].trim().split(' ')[0] : img.src;
      
      // Om base64/data URL
      if (imgUrl.startsWith('data:')) {
        imgUrl = imgUrl;
      }
      // Om relativ URL, gör absolut
      else if (imgUrl && !imgUrl.startsWith('http')) {
        imgUrl = new URL(imgUrl, window.location.href).href;
      }
      
      // Ignorera placeholder/logo-bilder
      if (imgUrl && (imgUrl.includes('placeholder') || imgUrl.includes('logo') || imgUrl.includes('icon'))) {
        imgUrl = null;
      }
    }
    
    if (name || number || imgUrl) {
      riders.push({
        number: number,
        name: name,
        imgUrl: imgUrl,
        element: card
      });
    }
  });
  
  // Strategi 2: Om vi inte hittade nog, leta efter alla bilder och försök matcha med text nära
  if (riders.length < 10) {
    console.log('⚠️ För få riders hittade, försöker alternativ metod...');
    const allImages = document.querySelectorAll('img');
    allImages.forEach(img => {
      // Hoppa över om redan hittad
      if (riders.some(r => r.imgUrl === img.src)) return;
      
      // Hoppa över placeholders
      if (img.src.includes('placeholder') || img.src.includes('logo') || img.src.includes('icon')) return;
      
      // Hoppa över väldigt små bilder (förmodligen ikoner)
      if (img.width && img.width < 50 && img.height && img.height < 50) return;
      
      // Hitta närmaste text-element som kan vara namn
      let name = null;
      let number = null;
      
      // Gå uppåt i DOM-trädet
      let parent = img.parentElement;
      let depth = 0;
      while (parent && depth < 5) {
        const text = parent.textContent.trim();
        
        // Försök hitta nummer
        if (!number) {
          const numMatch = text.match(/(?:^|[#\s])(\d{1,3})(?:\s|$)/);
          if (numMatch) number = parseInt(numMatch[1]);
        }
        
        // Försök hitta namn (efter nummer, före komma)
        if (!name && number && text.includes(number.toString())) {
          const parts = text.split(number.toString());
          if (parts[1]) {
            const namePart = parts[1].split(',')[0].split('\n')[0].trim();
            if (namePart.length > 2 && namePart.length < 30) {
              name = namePart;
            }
          }
        }
        
        // Alternativ: leta efter namn-el
        const nameEl = parent.querySelector('h1, h2, h3, h4, [class*="name"], [class*="Name"]');
        if (nameEl && !name) {
          name = nameEl.textContent.trim().split(',')[0].trim();
        }
        
        parent = parent.parentElement;
        depth++;
      }
      
      if (name || number || img.width > 100) {
        riders.push({
          number: number,
          name: name,
          imgUrl: img.srcset ? img.srcset.split(',')[0].trim().split(' ')[0] : img.src,
          element: img
        });
      }
    });
  }
  
  // Deduplicera
  const seen = new Set();
  const uniqueRiders = riders.filter(r => {
    const key = `${r.number || ''}_${r.name || ''}_${r.imgUrl || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return r.imgUrl && r.name; // Måste ha både bild och namn
  });
  
  console.log(`✅ Hittade ${uniqueRiders.length} riders med bilder`);
  console.table(uniqueRiders.map(r => ({
    Number: r.number,
    Name: r.name,
    'Image URL': r.imgUrl.substring(0, 50) + '...'
  })));
  
  // Bekräfta innan nedladdning
  const proceed = confirm(
    `Hittade ${uniqueRiders.length} riders med bilder.\n\n` +
    `Vill du ladda ner alla bilder?\n\n` +
    `Filnamnformat: {nummer}_{namn}.jpg\n` +
    `De kommer laddas ner till din Nedladdningar-mapp.`
  );
  
  if (!proceed) {
    console.log('❌ Nedladdning avbruten');
    return;
  }
  
  // Ladda ner alla bilder med fördröjning för att undvika rate limiting
  let downloaded = 0;
  uniqueRiders.forEach((rider, idx) => {
    setTimeout(() => {
      const filename = `${rider.number ? rider.number + '_' : ''}${slugify(rider.name)}.jpg`;
      
      console.log(`📥 Laddar ner (${idx + 1}/${uniqueRiders.length}): ${filename}`);
      
      if (rider.imgUrl.startsWith('data:')) {
        downloadDataURL(rider.imgUrl, filename);
      } else {
        downloadImage(rider.imgUrl, filename);
      }
      
      downloaded++;
      if (downloaded === uniqueRiders.length) {
        console.log('✅ Alla bilder nedladdade!');
        console.log('📋 Nästa steg:');
        console.log('   1. Flytta filerna till: static/riders/wsx/');
        console.log('   2. Kontrollera att filnamnen matchar formatet: {nummer}_{namn}.jpg');
      }
    }, idx * 300); // 300ms mellan varje nedladdning
  });
  
  // Returnera data för manuell kontroll
  return uniqueRiders.map(r => ({
    number: r.number,
    name: r.name,
    filename: `${r.number ? r.number + '_' : ''}${slugify(r.name)}.jpg`,
    imgUrl: r.imgUrl
  }));
})();

