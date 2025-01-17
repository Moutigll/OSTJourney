document.getElementById('load-more').addEventListener('click', function() {
	const button = this;
	const offset = parseInt(button.getAttribute('data-offset'), 10);
	fetch(`/profile/history?offset=${offset}`)
		.then(response => response.json())
		.then(data => {
			if (data.songs && data.songs.length > 0) {
				if (data.songs.length < 25) {
					button.style.display = 'none';
				}
				const tbody = document.getElementById('songs-tbody');
				data.songs.forEach(song => {
					const row = document.createElement('tr');
					row.innerHTML = `
						<td><a href="/?song=${song.song_id}" target="_blank">${song.song_id}</a></td>
						<td><a href="/?song=${song.song_id}" target="_blank">${song.title}</a></td>
						<td>${song.artist}</td>
						<td>${song.duration}</td>
					`;
					tbody.appendChild(row);
				});
				button.setAttribute('data-offset', offset + data.songs.length);
			} else {
				button.style.display = 'none';
			}
		})
		.catch(error => {
			console.error('Error loading more songs:', error);
		});
});

fetch('/profile/history/24h')
.then(response => response.json())
.then(data => {
	const hourlyCounts = data.hourly_counts;
	const labels = [];
	const counts = [];

	for (let hour = 0; hour < 24; hour++) {
		labels.push(hour + ':00');
		counts.push(hourlyCounts[hour]);
	}

	const ctx = document.getElementById('hourlyChart').getContext('2d');
	const hourlyChart = new Chart(ctx, {
		type: 'line',
		data: {
			labels: labels,
			datasets: [{
				label: 'Musics listened',
				data: counts,
				fill: false,
				borderColor: 'rgb(75, 192, 192)',
				tension: 0.1
			}]
		},
		options: {
			responsive: true, 
			scales: {
				x: {
					title: {
						display: true,
						text: 'Hour of the Day'
					}
				},
				y: {
					title: {
						display: true,
						text: 'Number of Songs'
					}
				}
			}
		}
	});
})
.catch(error => {
	console.error('Error fetching hourly data:', error);
});

//Activity Chart
function getColorForDuration(duration, minDuration, maxDuration, isDuration) {
	const range = maxDuration - minDuration;
	const step = range / 4;
	let level = Math.floor((duration - minDuration) / step);

	if (duration > 0 && level === 0) {
		level = 1;
	}

	level = Math.max(0, Math.min(level, 4));
	let r, g, b;

	if (!isDuration) {
		if (level === 0) {
			r = 22; g = 27; b = 34;
		} else if (level === 1) {
			r = 14; g = 68; b = 41;
		} else if (level === 2) {
			r = 0; g = 109; b = 50;
		} else if (level === 3) {
			r = 38; g = 166; b = 65;
		} else {
			r = 57; g = 211; b = 83;
		}
	} else {
		if (level === 0) {
			r = 22; g = 27; b = 34;
		} else if (level === 1) {
			r = 24; g = 48; b = 84;
		} else if (level === 2) {
			r = 26; g = 69; b = 135;
		} else if (level === 3) {
			r = 29; g = 90; b = 185;
		} else {
			r = 31; g = 111; b = 235;
		}
	}
	return `rgb(${r}, ${g}, ${b})`;
}

let yearData = {};
let year = null;
let isDuration = false;

document.getElementById('heatmap-song').classList.add('heatmap-song-active');

async function fetchActivityData() {
	try {
		const response = await fetch('/api/user_activity');
		const data = await response.json();

		if (data.status === 'success') {
			yearData = data.year_data;
			const years = Object.keys(yearData);

			const today = new Date();
			const lastYear = today.getFullYear() - 1;

			if (!yearData[lastYear]) {
				yearData[lastYear] = generateDefaultYearData(lastYear);
			}
			populateYearSelector(years, yearData);
			year = years[0];
			loadHeatmap(yearData, year, isDuration);
		} else {
			console.error('Error fetching user activity data:', data.message);
		}
	} catch (error) {
		console.error('Error fetching user activity data:', error);
	}
}

function generateDefaultYearData(year) {
	const defaultData = {};
	for (let month = 1; month <= 12; month++) {
		for (let day = 1; day <= 31; day++) {
			const currentDate = `${year}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
			defaultData[currentDate] = {
				total_duration: 0,
				total_songs: 0,
				formatted_duration: '0h 0m'
			};
		}
	}
	return {
		data: defaultData,
		min_duration: 0,
		max_duration: 0,
		min_songs: 0,
		max_songs: 0
	};
}

function populateYearSelector(years, yearData) {
	const yearSelect = document.getElementById('year');
	yearSelect.innerHTML = '';

	years.forEach(year => {
		const option = document.createElement('option');
		option.value = year;
		option.textContent = year;
		yearSelect.appendChild(option);
	});

	yearSelect.addEventListener('change', (event) => {
		year = event.target.value;
		loadHeatmap(yearData, year, isDuration);
	});
}

document.getElementById('heatmap-song').addEventListener('click', function () {
	if (isDuration) {
		isDuration = false;
		this.classList.add('heatmap-song-active');
		document.getElementById('heatmap-duration').classList.remove('heatmap-duration-active');
		loadHeatmap(yearData, year, isDuration);
		document.getElementById('heatmap-scale2').style.backgroundColor = 'rgb(14, 68, 41)';
		document.getElementById('heatmap-scale3').style.backgroundColor = 'rgb(0, 109, 50)';
		document.getElementById('heatmap-scale4').style.backgroundColor = 'rgb(38, 166, 65)';
		document.getElementById('heatmap-scale5').style.backgroundColor = 'rgb(57, 211, 83)';
	}
});

document.getElementById('heatmap-duration').addEventListener('click', function () {
	if (!isDuration) {
		isDuration = true;
		this.classList.add('heatmap-duration-active');
		document.getElementById('heatmap-song').classList.remove('heatmap-song-active');
		loadHeatmap(yearData, year, isDuration);
		document.getElementById('heatmap-scale2').style.backgroundColor = 'rgb(24, 48, 84)';
		document.getElementById('heatmap-scale3').style.backgroundColor = 'rgb(26, 69, 135)';
		document.getElementById('heatmap-scale4').style.backgroundColor = 'rgb(29, 90, 185)';
		document.getElementById('heatmap-scale5').style.backgroundColor = 'rgb(31, 111, 235)';
	}
});

function loadHeatmap(yearData, year, isDuration) {
	const heatmapContainer = document.getElementById('heatmap');
	heatmapContainer.innerHTML = '';

	const data = yearData[year].data;
	const minDuration = yearData[year].min_duration;
	const maxDuration = yearData[year].max_duration;
	const minSongs = yearData[year].min_songs;
	const maxSongs = yearData[year].max_songs;

	const firstDayOfYear = new Date(year, 0, 1);
	const lastDayOfYear = new Date(year, 11, 31);
	const weeksInYear = Math.ceil(((lastDayOfYear - firstDayOfYear) / (7 * 24 * 60 * 60 * 1000)) + 1);

	const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

	const thead = document.createElement('thead');
	const theadRow = document.createElement('tr');
	theadRow.innerHTML = '<th></th>';
	let previousMonth = -1;

	for (let week = 1; week <= weeksInYear; week++) {
		const startOfWeek = new Date(year, 0, (week - 1) * 7 + 1);
		const currentMonth = startOfWeek.getMonth();

		const th = document.createElement('th');
		if (currentMonth !== previousMonth) {
			const span = document.createElement('span');
			span.textContent = monthNames[currentMonth];
	  		th.appendChild(span);
			previousMonth = currentMonth;
		} else {
			th.textContent = '';
		}
		theadRow.appendChild(th);
	}
	thead.appendChild(theadRow);
	heatmapContainer.appendChild(thead);

	const tbody = document.createElement('tbody');
	const weekdays = ["", "Mon", "", "Wed", "", "Fri", ""];

	for (let weekdayIndex = 0; weekdayIndex < 7; weekdayIndex++) {
		const row = document.createElement('tr');

		const weekdayCell = document.createElement('td');
		weekdayCell.textContent = weekdays[weekdayIndex];
		row.appendChild(weekdayCell);

		for (let weekNumber = 1; weekNumber <= weeksInYear; weekNumber++) {
			const startOfWeek = new Date(year, 0, (weekNumber - 1) * 7 + 1);
			const dayOfWeek = weekdayIndex;
			const targetDate = new Date(startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay() + dayOfWeek));
			const currentDate = `${targetDate.getFullYear()}-${(targetDate.getMonth() + 1).toString().padStart(2, '0')}-${targetDate.getDate().toString().padStart(2, '0')}`;

			const cell = document.createElement('td');

			if (targetDate.getFullYear() !== parseInt(year)) {
				cell.style.backgroundColor = 'rgb(18, 18, 18)';
			} else if (data[currentDate]) {
				const { formatted_duration, total_duration, total_songs } = data[currentDate];
				const value = isDuration ? total_duration : total_songs;
				const minValue = isDuration ? minDuration : minSongs;
				const maxValue = isDuration ? maxDuration : maxSongs;

				const color = getColorForDuration(value, minValue, maxValue, isDuration);
				cell.style.backgroundColor = color;
				cell.title = `Date: ${currentDate}\nDuration: ${formatted_duration}\nSongs: ${total_songs}`;
			} else {
				cell.style.backgroundColor = 'rgb(18, 18, 18)';
			}

			row.appendChild(cell);
		}

		tbody.appendChild(row);
	}
	heatmapContainer.appendChild(tbody);
}

fetchActivityData();
