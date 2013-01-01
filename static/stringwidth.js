function getWidth(text)
{
	var spanElement = document.createElement(’span’);
	spanElement.style.whiteSpace = “nowrap”;
	spanElement.innerHTML = text;
	document.body.appendChild(spanElement);
	var width = spanElement.offsetWidth;
	document.body.removeChild(spanElement);

	return width;
}
