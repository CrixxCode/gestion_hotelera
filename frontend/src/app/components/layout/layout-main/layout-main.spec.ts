import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LayoutMain } from './layout-main';

describe('LayoutMain', () => {
  let component: LayoutMain;
  let fixture: ComponentFixture<LayoutMain>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LayoutMain]
    })
    .compileComponents();

    fixture = TestBed.createComponent(LayoutMain);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
