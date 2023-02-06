/* global d3 */
var myd3 = function () {

    var myd3 = {};
	myd3.config = {
		b_size: 40,
		n_padding: 10,
		cols: 16,
		stroke: 2,
		interactive: false
	};

	function Encoding(dataset, config, widget) {

		var self = this;
		
		this.data = dataset;
		this.config = Object.assign({}, myd3.config, config);
		
		var rows = this.data.length / this.config.cols;
		var nibblesPerRow = this.config.cols / 4;
		var width = this.config.cols * this.config.b_size + (nibblesPerRow - 1) * this.config.n_padding + this.config.stroke;
		var height = rows * this.config.b_size + (rows - 1) * this.config.n_padding + this.config.stroke;
		
		this.widget = d3.select('#' + widget)
			.style('display', 'inline-block');
		
		this.svg = this.widget.append('svg')
			.style('width', width + "px").style('height', height + "px");
			// .style('width', "100%").style('height', "100%");
			
		this.f_translate = function(d, i) {
			var col = i % 16;
			var nibble = parseInt(col / 4);
			var row = parseInt(i / 16);
			var x = col * self.config.b_size + nibble * self.config.n_padding + 1;
			var y = row * (self.config.b_size + self.config.n_padding) + 1;
			return 'translate(' + x + ', ' + y + ')'; 
		};
		this.f_bgColor = function(d) {
			switch(d.class) {
				case "register_sel":
				case "register_bitflip":
					return '#88FF88';
				case "opcode_sel":
				case "opcode_bitflip":
					return '#A5A5A5';
				case "dontcare_sel":
				case "dontcare_bitflip":
					return '#171717';
				case "immediate_sel":
				case "immediate_bitflip":
					return '#8888FF';
					
				case "register":
					return '#D5FFD5';
				case "opcode":
					return '#DDDDDD';
				case "dontcare":
					return '#505050';
				case "immediate":
					return '#D5D5FF';
			}
		};
		this.f_bgImage = function(d) {
			if (d.class.endsWith("_bitflip")) {
				return '/static/images/bitflip.png';
			}
			return '';
		}
		this.f_txtColor = function(d) {
			switch(d.class) {
				case "register":
					return 'black';
				case "opcode":
					return 'black';
				case "dontcare":
					return 'white';
				case "immediate":
					return 'black';
			}
		};
		this.f_txt = function(d) {
			if (d.class.endsWith("_bitflip")) {
				return '';
			}
			return d.txt;
		};
		
		//this.g = this.svg.selectAll('g');
		
		this.update();
		
		return this;
	}
	Encoding.prototype.update = function() {
		var self = this;
		
		this.rect = this.svg.selectAll('rect').data(self.data);
		this.image = this.svg.selectAll('image').data(self.data);
		this.text = this.svg.selectAll('text').data(self.data);
		
		this.rect.transition()
			.attr('fill', this.f_bgColor);
		this.image.transition()
			.attr('xlink:href', this.f_bgImage);
		this.text.transition()
			.attr('fill', this.f_txtColor)
			.text(this.f_txt);		
		
		var r = this.rect.enter().append('rect')
			.attr('transform', this.f_translate)
			.attr('width', this.config.b_size)
			.attr('height', this.config.b_size)
	        .attr('stroke', '#000000')
			.attr("stroke-width", '2px')
			.attr('class', 'selectable')
			.attr('fill', this.f_bgColor);

		var i = this.image.enter().append('image')
			.attr('transform', this.f_translate)
			.attr('x', 2)
			.attr('y', 2)
			.attr('width', this.config.b_size - 4)
			.attr('height', this.config.b_size - 4)
			.attr('xlink:href', this.f_bgImage);
			
		var t = this.text.enter().append('text')
			.attr('transform', this.f_translate)
			.attr('x', (this.config.b_size / 2))
			.attr('y', (this.config.b_size / 2))
			.attr('text-anchor', 'middle')
			.attr('dominant-baseline', 'central')
			.attr('fill', this.f_txtColor)
			.text(this.f_txt); 
			
		if (this.config.interactive) {
			r.on('click', function(d, i) { toggle(i); });
			i.on('click', function(d, i) { toggle(i); });
			t.on('click', function(d, i) { toggle(i); });
		}
		
		this.rect.exit().remove();
		this.image.exit().remove();
		this.text.exit().remove();
	
		//this.ng.exit().remove();
	/*
		new_g.append('rect')
			.attr('width', this.config.b_size)
			.attr('height', this.config.b_size)
			.attr('fill', this.f_bgColor)
	        .attr('stroke', '#000000')
			.attr("stroke-width", '2px');
		
		new_g.append('image')
			.attr('x', 2)
			.attr('y', 2)
			.attr('width', this.config.b_size - 4)
			.attr('height', this.config.b_size - 4)
			.attr('xlink:href', this.f_bgImage);
		
		new_g.append('text')
			.attr('fill', this.f_txtColor)
			.attr('x', (this.config.b_size / 2))
			.attr('y', (this.config.b_size / 2))
			.attr('text-anchor', 'middle')
			.attr('alignment-baseline', 'central')
			.text(this.f_txt); */
			
		//g.exit().remove();
	};
	
    return {
		enc: Encoding
    };
}();