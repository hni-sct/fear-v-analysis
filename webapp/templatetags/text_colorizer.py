from django import template
register = template.Library()


def desccolor(value, d):
    value = value.replace('Rd', '<font color="' + d[d['Rd']] + '"><b>Rd</b></font>')
    value = value.replace('Rs', '<font color="' + d[d['Rs']] + '"><b>Rs</b></font>')
    value = value.replace('Rn', '<font color="' + d[d['Rn']] + '"><b>Rn</b></font>')
    value = value.replace('immediate', '<font color="' + d[d['immediate']] + '"><b>immediate</b></font>')
    return value


def paramcolor(pname, d):
    try:
        stage1 = d[pname]
        return d[stage1]
    except:
        return "#F0E68C"


register.filter('desccolor', desccolor)
register.filter('paramcolor', paramcolor)
